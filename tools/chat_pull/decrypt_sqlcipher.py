#!/usr/bin/env python3
"""decrypt_sqlcipher —— 用密钥候选对 SQLCipher 库做页级解密（QQ NT / 微信 4.x）。

v2：参数空间全暴破——页大小 × IV 距页尾距离 × 页1起始偏移 × raw/KDF 密钥变体。
判定：页 1 解密后出现 SQLite format 3 魔数。命中后整库解密落盘并用 sqlite3 验证。

用法：python decrypt_sqlcipher.py --db <加密库> --keys candidates.json --out <输出路径>
"""

import argparse, hashlib, io, json, os, sys

from Crypto.Cipher import AES

MAGIC = b'SQLite format 3\x00'
IV_LEN = 16
PAGE_SIZES = [4096, 8192, 1024, 16384, 32768, 512]
TAIL_DISTS = [80, 64, 48, 96, 112, 128, 32, 144, 160, 40, 24, 16]   # IV 距页尾的常见 reserve 距离

def kdf_variants(key_hex: str, salt: bytes, cache: dict):
    """(描述, 32字节密钥) 候选；按 (hex, 变体) 缓存，页布局重试时零成本。"""
    kk = (key_hex, salt)
    if kk in cache:
        return cache[kk]
    out = []
    raw = bytes.fromhex(key_hex)
    if len(raw) == 32:
        out.append(('raw', raw))
    for iters, h in ((256000, 'sha512'), (256000, 'sha1'), (64000, 'sha1')):
        try:
            out.append((f'kdf-{h}-{iters}', hashlib.pbkdf2_hmac(h, key_hex.encode(), salt, iters, 32)))
        except Exception:
            pass
    cache[kk] = out
    return out

def layouts(P: int):
    """(iv_off, start) 组合；start= 页1密文起始（16=salt 后），其余页恒 0。"""
    for d in TAIL_DISTS:
        iv_off = P - d
        if iv_off > IV_LEN:
            yield iv_off, (16 if iv_off > 16 else 0)

def try_page1(db: bytes, key: bytes, P: int, iv_off: int, start: int) -> bool:
    iv = db[iv_off:iv_off + IV_LEN]
    pt = AES.new(key, AES.MODE_CBC, iv).decrypt(db[start:iv_off])
    return pt.startswith(MAGIC)

def decrypt_db(db: bytes, key: bytes, P: int, iv_off: int) -> bytes:
    out = bytearray()
    for i in range(0, len(db) // P):
        page = db[i * P:(i + 1) * P]
        iv = page[iv_off:iv_off + IV_LEN]
        start = 16 if i == 0 else 0
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(page[start:iv_off])
        out += (MAGIC + pt) if i == 0 else pt
    return bytes(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--keys', required=True, help='keyscan 输出的 json；也接受单条 64hex 串')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    if os.path.isfile(a.keys):
        cands = json.load(io.open(a.keys, encoding='utf-8'))
    else:
        cands = [a.keys.strip()]
    cands = sorted({c.strip().lower() for c in cands if len(c.strip()) == 64})
    db = open(a.db, 'rb').read()
    salt = db[:16]
    print(f"{a.db}: {len(db)/1e6:.1f} MB, salt={salt.hex()[:16]}.., 候选 {len(cands)}", flush=True)
    cache: dict = {}

    hit = None
    def attempt(hexkey, variants, tag, n):
        for label, key in variants:
            for P in PAGE_SIZES:
                if P > len(db): continue
                for iv_off, start in layouts(P):
                    try:
                        if try_page1(db, key, P, iv_off, start):
                            return (hexkey, label, key, P, iv_off)
                    except ValueError:
                        continue
        if n % 200 == 0: print(f"  ..[{tag}] 已试 {n}", flush=True)
        return None

    # 第一遍：raw key（快）
    for n, hexkey in enumerate(cands):
        hit = attempt(hexkey, kdf_variants(hexkey, salt, cache)[:1], 'raw', n)
        if hit: break
    # 第二遍：KDF 变体（慢，每候选 3 次 PBKDF2，跨布局复用缓存）
    if not hit:
        print('raw 未命中，转 KDF 变体（慢，预计数十分钟）……', flush=True)
        for n, hexkey in enumerate(cands):
            hit = attempt(hexkey, kdf_variants(hexkey, salt, cache)[1:], 'kdf', n)
            if hit: break

    if not hit:
        sys.exit('全部候选 × 全布局未命中——密钥不在候选集里，或非 SQLCipher 4 常见参数。')

    hexkey, label, key, P, iv_off = hit
    print(f"命中：key={hexkey[:12]}.., {label}, page={P}, iv@{iv_off}", flush=True)
    plain = decrypt_db(db, key, P, iv_off)
    io.open(a.out, 'wb').write(plain)
    import sqlite3
    con = sqlite3.connect(a.out)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 12")]
    con.close()
    print(f"解密完成 -> {a.out}\n前 12 张表：{tables}", flush=True)

if __name__ == '__main__':
    main()
