import json, glob, os, re

TMP = os.path.join(os.environ.get("TEMP", r"C:\Users\mc158\AppData\Local\Temp"), "opus-style")
base = os.path.expanduser("~/.claude/projects")
CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

def lang_of(t):
    cjk = len(CJK.findall(t))
    latin = len(re.findall(r'[A-Za-z]', t))
    if cjk + latin == 0: return "other"
    return "zh" if cjk / (cjk + latin) >= 0.15 else "en"

out = open(os.path.join(TMP, "opus_all.jsonl"), "w", encoding="utf-8")
counts = {"zh": 0, "en": 0, "other": 0}
for fp in sorted(glob.glob(os.path.join(base, "*", "*.jsonl"))):
    proj = os.path.basename(os.path.dirname(fp))
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "opus" not in line: continue
            try: obj = json.loads(line)
            except Exception: continue
            if obj.get("type") != "assistant": continue
            m = obj.get("message") or {}
            if "opus" not in (m.get("model") or ""): continue
            side = obj.get("isSidechain", False)
            ts = obj.get("timestamp", "")
            blocks = m.get("content") or []
            if isinstance(blocks, str): blocks = [{"type": "text", "text": blocks}]
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") != "text": continue
                t = (b.get("text") or "").strip()
                if not t: continue
                t = re.sub(r'\n{3,}', '\n\n', t)
                lg = lang_of(t)
                counts[lg] += 1
                rec = {"p": proj, "f": os.path.basename(fp), "t": ts, "s": int(side),
                       "l": len(t), "lang": lg, "text": t[:6000]}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
out.close()
print(counts)
