import sqlite3, os, json, re

TMP = os.path.join(os.environ.get("TEMP", r"C:\Users\mc158\AppData\Local\Temp"), "opus-style")
db = os.path.expanduser("~/.local/share/opencode/opencode.db")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()

CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
def lang_of(t):
    cjk = len(CJK.findall(t)); latin = len(re.findall(r'[A-Za-z]', t))
    if cjk + latin == 0: return "other"
    return "zh" if cjk / (cjk + latin) >= 0.15 else "en"

# load text parts grouped by message_id
parts = {}
for mid, data in cur.execute("SELECT message_id, data FROM part"):
    try: p = json.loads(data)
    except Exception: continue
    if p.get("type") != "text": continue
    t = (p.get("text") or "").strip()
    if not t: continue
    parts.setdefault(mid, []).append(t)

counts = {}
out = open(os.path.join(TMP, "ds_all.jsonl"), "w", encoding="utf-8")
for mid, data in cur.execute("SELECT id, data FROM message"):
    try: m = json.loads(data)
    except Exception: continue
    if m.get("role") != "assistant": continue
    prov, model = m.get("providerID") or "", m.get("modelID") or ""
    if "deepseek" not in (prov + "/" + model).lower(): continue
    key = f"{prov}/{model}"
    counts[key] = counts.get(key, 0) + 1
    ts = m.get("time", {}).get("created", 0)
    import datetime
    day = datetime.datetime.utcfromtimestamp(ts/1000).strftime("%Y-%m-%d") if ts else ""
    for t in parts.get(mid, []):
        t = re.sub(r'\n{3,}', '\n\n', t)
        out.write(json.dumps({"m": key, "d": day, "l": len(t), "lang": lang_of(t), "text": t[:6000]}, ensure_ascii=False) + "\n")
out.close()
print("messages per model:", json.dumps(counts, indent=1, ensure_ascii=False))
con.close()
