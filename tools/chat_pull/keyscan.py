#!/usr/bin/env python3
"""keyscan —— 从指定进程内存中收集 64 位十六进制字符串（SQLCipher 密钥候选）。

只读内存，不写入目标进程。QQ NT / 微信 4.x 的密钥都以 hex 字符串形式驻留内存，
扫描后交给 decrypt_sqlcipher.py 对库文件逐一验证。
仅用于读取本人自己账号的数据。

用法：python keyscan.py --proc QQ.exe --proc Weixin.exe --out candidates.json
"""

import argparse, ctypes, json, os, re
import ctypes.wintypes as wintypes

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x20, 0x40}          # PAGE_READONLY/READWRITE/EXECUTE_READ/EXECUTE_READWRITE
HEX64 = re.compile(rb'[0-9a-f]{64}')
MAX_REGION = 96 * 1024 * 1024                  # 单区域上限
MAX_TOTAL = 8 * 1024 * 1024 * 1024             # 每进程扫描总量上限

class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p),
                ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wintypes.DWORD),
                ('RegionSize', ctypes.c_size_t),
                ('State', wintypes.DWORD),
                ('Protect', wintypes.DWORD),
                ('Type', wintypes.DWORD)]

def pids_by_name(names: set[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    TH32CS_SNAPPROCESS = 0x2
    class PE32(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_char * 260)]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    e = PE32(); e.dwSize = ctypes.sizeof(PE32)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        name = e.szExeFile.decode(errors='replace')
        if name in names:
            out.setdefault(name, []).append(e.th32ProcessID)
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return out

def scan_pid(pid: int) -> set[str]:
    found: set[str] = set()
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        print(f"  pid {pid}: OpenProcess 失败（err={ctypes.get_last_error()}）")
        return found
    addr, total, region_n = 0, 0, 0
    mbi = MBI(); size = ctypes.sizeof(mbi)
    while total < MAX_TOTAL:
        r = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), size)
        if not r: break
        base, rsize = mbi.BaseAddress or 0, mbi.RegionSize or 0
        if mbi.State == MEM_COMMIT and mbi.Protect in READABLE and 0 < rsize <= MAX_REGION:
            buf = (ctypes.c_char * rsize)()
            got = ctypes.c_size_t(0)
            if k32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, rsize, ctypes.byref(got)):
                data = buf.raw[:got.value]
                for m in HEX64.finditer(data):
                    found.add(m.group().decode())
                total += rsize; region_n += 1
        addr = base + rsize
        if addr > 0x7FFFFFFF0000: break
    k32.CloseHandle(h)
    print(f"  pid {pid}: 扫描 {total/1e6:.0f} MB / {region_n} 区域，候选 {len(found)}")
    return found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--proc', action='append', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cands: set[str] = set()
    for name, pids in pids_by_name(set(a.proc)).items():
        print(f"{name}: {pids}")
        for pid in pids:
            cands |= scan_pid(pid)
    json.dump(sorted(cands), open(a.out, 'w'))
    print(f"共 {len(cands)} 个候选 -> {a.out}")

if __name__ == '__main__':
    main()
