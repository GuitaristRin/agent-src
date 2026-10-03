#!/usr/bin/env python3
"""chat_pull —— 从微信/QQ 导出物中抽取「指定群聊 + 本人账号 + 纯文本」的消息。

设计契约（与 user-voice 原文隔离规程一致）：
  1. 原文永不写入 agent-src 仓库——输出目录默认在 ~/Documents/chat-corpus/，脚本启动时强制校验；
  2. 只保留本人账号发出的纯文本消息（微信 IsSender/类型过滤，QQ 按 own_uin 过滤）；
  3. 保留 burst 分界：间隔 <=BURST_GAP 秒的连发算一段（结构特征全在这里）；
  4. 导出前脱敏：手机号 / 身份证 / 长数字串 / password 类字段打码。

适配层（按数据来源自动选择）：
  A. PyWxDump / 留痕(MemoTrace) 的 CSV 导出目录
  B. 已解密的微信 MSG SQLite 库（3.9 架构；4.0 请先用 wechat-dump-rs 等工具导出）
  C. 已解密的 QQ NT nt_msg.db（列名不确定时用 --inspect 先看结构）
  D. 手动复制的纯文本块（微信/QQ PC 端多选消息后复制粘贴成 txt，丢进 输出目录/manual/）

用法：
  python chat_pull.py --config chat_pull.toml            # 全量跑
  python chat_pull.py --inspect <某个.sqlite/.db>        # 看库的表和列（适配新架构用）
"""

from __future__ import annotations
import argparse, csv, datetime, glob, io, json, os, re, sqlite3, sys

try:
    import tomllib
except ImportError:  # py3.10-
    tomllib = None

BURST_GAP = 120          # 秒；连发分段的间隔上限
REDACT = [
    (re.compile(r'1[3-9]\d{9}'), '[手机号]'),
    (re.compile(r'\b\d{17}[\dXx]\b'), '[证件号]'),
    (re.compile(r'(?i)(password|passwd|密码|口令)[^\s]{0,4}[:：]\s*\S+'), r'\1: [已抹]'),
    (re.compile(r'\b\d{6,}\b(?![-/])'), '[数字串]'),   # 兜底：6 位以上孤立纯数字（QQ 号、订单号等）
]

def redact(s: str) -> str:
    for pat, rep in REDACT:
        s = pat.sub(rep, s)
    return s

def in_repo_guard(out_dir: str) -> str:
    """原文不入库：输出目录不得位于本仓库内部（仓库根按 .git 向上判定，不依赖目录名）。"""
    d = os.path.dirname(os.path.abspath(__file__))
    repo = None
    while True:
        if os.path.isdir(os.path.join(d, '.git')):
            repo = d; break
        parent = os.path.dirname(d)
        if parent == d: break
        d = parent
    real_out = os.path.realpath(out_dir)
    if repo:
        real_repo = os.path.realpath(repo)
        if real_out == real_repo or real_out.startswith(real_repo + os.sep):
            sys.exit(f"拒绝：输出目录 {out_dir} 在仓库内。原文不入库（user-voice 原文隔离规程）。")
    os.makedirs(real_out, exist_ok=True)
    return real_out

def keep_text(content: str) -> str | None:
    """纯文本过滤：剥掉 XML、引用头、残余标签与媒体占位。"""
    if not content: return None
    c = content.strip()
    if c.startswith('<?xml') or c.startswith('<msg'): return None
    c = re.sub(r'引用\s*[^\n]*的消息\s*[:：][^\n]*', '', c)      # 微信引用头
    c = re.sub(r'<[^>]{1,80}>', '', c)                            # 残余内联标签
    c = re.sub(r'(\[图片\]|\[语音\]|\[视频\]|\[文件\][^\n]*|查看图片)', '', c).strip()
    return c or None

def burst_lines(messages: list[dict]) -> str:
    """messages 按时间升序；间隔 >BURST_GAP 秒即开新段，段首带时间戳。ts 统一为毫秒。"""
    out, cur, last_ts = [], [], None
    for m in messages:
        if last_ts is None or (m['ts'] - last_ts) > BURST_GAP * 1000:
            if cur: out.append('\n'.join(cur))
            cur = [f"[{m['dt']}]"]
        cur.append(m['text'])
        last_ts = m['ts']
    if cur: out.append('\n'.join(cur))
    return '\n\n'.join(out) + '\n'

def daterange(ts_ms: int, s: str, e: str) -> bool:
    if not s and not e: return True
    d = datetime.datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d')
    return (not s or d >= s) and (not e or d <= e)

def group_ok(talker: str, groups: list[str]) -> bool:
    return (not groups) or any(g and (g in talker or talker in g) for g in groups)

# ---------- 适配层 A：PyWxDump / MemoTrace CSV ----------
CSV_COLS = {  # 宽松列名映射（小写去下划线比对）
    'talker':  ('strtalker', 'talker', '群名'),
    'isend':   ('issender', 'issend', 'issenderflag'),
    'type':    ('type', 'msgtype'),
    'content': ('strcontent', 'content', '消息内容'),
    'ts':      ('createtime', 'timestamp', 'msgtime'),
}

def match_cols(header: list[str]) -> dict | None:
    low = [h.strip().lower().replace('_', '').replace(' ', '') for h in header]
    got = {}
    for key, cands in CSV_COLS.items():
        for cand in cands:
            if cand in low:
                got[key] = low.index(cand); break
    return got if {'talker', 'isend', 'content', 'ts'} <= got.keys() else None

def add_msg(buckets: dict, key: str, ts_ms: int, text: str):
    buckets.setdefault(key, []).append(
        {'ts': ts_ms, 'dt': datetime.datetime.fromtimestamp(ts_ms / 1000).strftime('%m-%d %H:%M'),
         'text': text})

def load_csv_dir(root: str, wc: dict) -> dict[str, list]:
    buckets: dict[str, list] = {}
    n = 0
    for fp in glob.glob(os.path.join(root, '**', '*.csv'), recursive=True):
        with open(fp, encoding='utf-8-sig', errors='replace', newline='') as f:
            rows = list(csv.reader(f))
        if not rows: continue
        cols = match_cols(rows[0])
        if not cols: continue
        for r in rows[1:]:
            if len(r) <= max(cols.values()): continue
            try:
                v = float(r[cols['ts']]); ts = int(v * (1000 if v < 1e11 else 1))
            except Exception: continue
            if r[cols['isend']].strip() not in ('1', 'true', 'True'): continue
            if r[cols['type']].strip() not in ('1', 'text', 'Text', ''): continue
            if not group_ok(r[cols['talker']], wc.get('groups', [])): continue
            if not daterange(ts, wc.get('start_date', ''), wc.get('end_date', '')): continue
            text = keep_text(r[cols['content']])
            if not text: continue
            add_msg(buckets, r[cols['talker']], ts, redact(text))
            n += 1
    print(f"  [csv] {root}: {n} 条本人文本")
    return buckets

# ---------- 适配层 B：已解密的微信 MSG 库（3.9 架构） ----------
def load_wechat_db(db: str, wc: dict) -> dict[str, list]:
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    buckets: dict[str, list] = {}
    n = 0
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE 'msg%'")]
    for t in tables:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info('{t}')")]
        low = [c.lower().replace('_', '') for c in cols]
        if 'strtalker' not in low or 'strcontent' not in low: continue
        ci = {k: cols[low.index(v)] for k, v in
              {'talker': 'strtalker', 'isend': 'issender', 'content': 'strcontent',
               'ts': 'createtime', 'type': 'type'}.items() if v in low}
        if not {'talker', 'isend', 'content', 'ts', 'type'} <= ci.keys(): continue
        where = f"WHERE {ci['isend']}=1 AND {ci['type']}=1"
        args: list = []
        if wc.get('groups'):
            where += " AND (" + " OR ".join(f"{ci['talker']} LIKE ?" for _ in wc['groups']) + ")"
            args = [f"%{g}%" for g in wc['groups']]
        for talker, ts, content in con.execute(f"SELECT {ci['talker']},{ci['ts']},{ci['content']} FROM {t} {where}", args):
            ts = int(ts) * (1000 if int(ts) < 1e11 else 1)
            if not daterange(ts, wc.get('start_date', ''), wc.get('end_date', '')): continue
            text = keep_text(content)
            if not text: continue
            add_msg(buckets, talker, ts, redact(text))
            n += 1
    con.close()
    print(f"  [wechat-db] {os.path.basename(db)}: {n} 条")
    return buckets

# ---------- 适配层 C：QQ NT（解密后的 nt_msg.db，结构用 --inspect 确认） ----------
def load_qq_nt(db: str, qq: dict) -> dict[str, list]:
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    buckets: dict[str, list] = {}
    own = str(qq.get('own_uin', '') or '')
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND lower(name) LIKE '%group%'")]
    for t in tables:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info('{t}')")]
        low = {c.lower(): c for c in cols}
        sender_c = next((low[c] for c in sorted(low) if 'sender' in c), None)
        content_c = next((low[c] for c in sorted(low) if 'content' in c), None)
        time_c = next((low[c] for c in sorted(low) if 'time' in c), None)
        if not (sender_c and content_c and time_c): continue
        where, args = '', []
        if own:
            where, args = f"WHERE {sender_c} = ?", [own]
        try:
            rows = con.execute(f"SELECT {time_c},{content_c} FROM '{t}' {where}", args).fetchall()
        except sqlite3.Error as e:
            print(f"  [qq-nt] 跳过 {t}: {e}"); continue
        kept = 0
        for ts, raw in rows:
            try: ts = int(ts) * (1000 if int(ts) < 1e11 else 1)
            except Exception: continue
            text = None
            try:  # NT 的 content 常是 JSON 数组
                j = json.loads(raw)
                if isinstance(j, list):
                    text = ''.join(seg.get('textContent', '') for seg in j if isinstance(seg, dict))
            except Exception:
                text = raw
            text = keep_text(text or '')
            if not text: continue
            if not group_ok(t, qq.get('groups', [])): continue
            if not daterange(ts, qq.get('start_date', ''), qq.get('end_date', '')): continue
            add_msg(buckets, t, ts, redact(text))
            kept += 1
        print(f"  [qq-nt] {t}: {kept} 条")
    con.close()
    return buckets

# ---------- 适配层 D：手动复制的纯文本 ----------
def _read_text(fp: str) -> str:
    raw = open(fp, "rb").read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n")

def load_manual_txt(fp: str, own_names: set[str]) -> dict[str, list]:
    """三种模式自动识别（编码自动回退 utf-8→gbk）：
    A. 微信年月日模式：块 = 昵称行 + 「2026年10月03日 20:47」行 + 内容行；
    B. 头行模式：块首行 = 名字 + ISO 日期时间（PC 复制格式），按 own_names 认领；
    C. 裸文本模式：QQ 多选复制——无发送者行，消息以 3+ 换行分隔，
       「2026/10/01」日期行做日界；内容默认全部属于文件主人。"""
    raw = _read_text(fp)
    key = os.path.splitext(os.path.basename(fp))[0]
    msgs: list[dict] = []
    ISO_HEAD = re.compile(r"^\s*\S.{0,18}\s+\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?\s*$")
    WXD = re.compile(r"^(20\d{2})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2}(?::\d{2})?)?$")

    if re.search(r"\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}", raw):
        # A. 微信年月日：昵称行 + 日期行 + 内容
        pending = ""
        state = {"dt": None, "buf": []}
        def flush_w():
            if state["dt"] and state["buf"] and pending and pending in own_names:
                text = keep_text("\n".join(state["buf"]).strip())
                if text:
                    msgs.append({"ts": int(state["dt"].timestamp() * 1000),
                                 "dt": state["dt"].strftime("%m-%d %H:%M"), "text": redact(text)})
            state["dt"], state["buf"] = None, []
        for line in raw.split("\n"):
            if not line.strip():
                flush_w(); continue
            m = WXD.match(line.strip())
            if m:
                y, mo, dd, t = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4) or "00:00"
                try:
                    state["dt"] = datetime.datetime(int(y), mo, dd, *map(int, t.split(":")))
                except ValueError:
                    state["dt"] = None
                state["buf"] = []
            elif state["dt"] is None and len(line.strip()) <= 20:
                pending = line.strip()
            elif state["dt"] is not None:
                state["buf"].append(line.strip())
        flush_w()
        return {key: sorted(msgs, key=lambda x: x["ts"])} if msgs else {}

    if ISO_HEAD.search(raw):
        # B. 头行模式
        state = {"sender": "", "dt": "", "buf": []}
        def flush_h():
            sender, dt, buf = state["sender"], state["dt"], state["buf"]
            if dt and buf and sender in own_names:
                ts = 0
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
                    try:
                        ts = int(datetime.datetime.strptime(dt.strip(), fmt).timestamp() * 1000); break
                    except ValueError: pass
                text = keep_text("\n".join(buf).strip())
                if text:
                    msgs.append({"ts": ts, "dt": dt[-14:], "text": redact(text)})
            state["sender"], state["dt"], state["buf"] = "", "", []
        for line in raw.split("\n"):
            if not line.strip():
                flush_h(); continue
            m = re.match(r"^\s*(?P<name>.+?)\s*[ \[（]?\s*(?P<y>\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(?P<t>\d{1,2}:\d{2}(?::\d{2})?)?", line)
            if m and m.group("y"):
                flush_h()
                state["sender"] = m.group("name").strip()
                state["dt"] = (m.group("y") + " " + (m.group("t") or "00:00")).replace("/", "-")
                state["buf"] = []
            else:
                state["buf"].append(line.strip())
        flush_h()
        return {key: sorted(msgs, key=lambda x: x["ts"])} if msgs else {}

    # C. 裸文本模式（QQ 多选复制）
    day, k = "", 0
    for block in re.split(r"\n{3,}", raw):
        b = block.strip("\n").strip()
        if not b: continue
        lines = b.split("\n")
        if len(lines) >= 1 and re.fullmatch(r"(20\d{2})[/年.](\d{1,2})[/月.](\d{1,2})\s*日?", lines[0].strip()):
            y, mm, dd = re.findall(r"\d+", lines[0])
            day = f"{y}-{int(mm):02d}-{int(dd):02d}"
            lines = lines[1:]
            b = "\n".join(lines).strip()
            if not b: continue
        text = keep_text(b)
        if not text: continue
        ts = k
        if day:
            try: ts = int(datetime.datetime.strptime(day, "%Y-%m-%d").timestamp() * 1000) + k
            except ValueError: pass
        k += 1
        msgs.append({"ts": ts, "dt": day or f"blk{k:04d}", "text": text})
    return {key: msgs} if msgs else {}

# ---------- inspect ----------
def inspect(db: str):
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 200"):
        cols = [f"{c[1]}({c[2]})" for c in con.execute(f"PRAGMA table_info('{t}')")]
        try: n = con.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
        except Exception: n = '?'
        print(f"{t} [{n}]: {', '.join(cols)}")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=os.path.join(os.path.dirname(__file__), 'chat_pull.toml'))
    ap.add_argument('--inspect', help='查看某个 SQLite 库的表结构后退出')
    args = ap.parse_args()
    if args.inspect:
        inspect(args.inspect); return

    if tomllib is None: sys.exit('需要 Python 3.11+（tomllib）')
    cfg = tomllib.loads(io.open(args.config, encoding='utf-8').read())
    own = set(cfg.get('output', {}).get('own_names', []))
    out = in_repo_guard(cfg['output']['dir'])
    wc, qq = cfg.get('wechat', {}), cfg.get('qq', {})

    all_sources: dict[str, dict[str, list]] = {}
    for root in wc.get('export_roots', []) or []:
        all_sources.setdefault('wechat', {}).update(load_csv_dir(root, wc))
    for db in wc.get('decrypted_dbs', []) or []:
        all_sources.setdefault('wechat', {}).update(load_wechat_db(db, wc))
    for db in qq.get('decrypted_dbs', []) or []:
        all_sources.setdefault('qq', {}).update(load_qq_nt(db, qq))
    for fp in glob.glob(os.path.join(out, 'manual', '*.txt')):
        all_sources.setdefault('manual', {}).update(load_manual_txt(fp, own))

    for plat, buckets in all_sources.items():
        for name, msgs in buckets.items():
            if not msgs: continue
            msgs.sort(key=lambda m: m['ts'])
            safe = re.sub(r'[\\/:*?"<>|\s@]+', '_', name)[:40]
            fp = os.path.join(out, f"{plat}_{safe}.txt")
            io.open(fp, 'w', encoding='utf-8', newline='\n').write(burst_lines(msgs))
            print(f"  -> {fp}  ({len(msgs)} 条 / {sum(len(m['text']) for m in msgs)} 字符)")
    print(f"\n完成。原文在 {out}（仓库外，勿移入 agent-src）。")

if __name__ == '__main__':
    main()
