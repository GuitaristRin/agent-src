import json, glob, os, re, sqlite3, datetime

TMP = os.path.join(os.environ.get("TEMP", r"C:\Users\mc158\AppData\Local\Temp"), "opus-style")
out = open(os.path.join(TMP, "user_corpus.jsonl"), "w", encoding="utf-8")
n = {}

def lang(t):
    cjk = len(re.findall(r'[\u4e00-\u9fff]', t))
    lat = len(re.findall(r'[A-Za-z]', t))
    return "zh" if cjk > 0 and cjk >= 0.15 * (cjk + lat) else "en"

TASKBOOK = re.compile(r'^#{1,3}\s*(Objective|Important Details|Work State|Background|Task|要做的事|背景|目标)', re.M)
NOISE = re.compile(r'^(<|Caveat:|\[Request interrupted|\[Omitted)')

def is_worktree(dirp):
    d = (dirp or "").replace("\\", "/")
    return "/wt/" in d or d.rstrip("/").endswith("-wt") or "/.oc/" in d

def clean(t):
    t = re.sub(r'<system-reminder>.*?</system-reminder>', '', t, flags=re.S)
    t = re.sub(r'<command-(name|args|message)>.*?</command-(name|args|message)>', '', t, flags=re.S)
    t = re.sub(r'<local-command[^>]*>.*?</local-command[^>]*>', '', t, flags=re.S)
    return re.sub(r'\n{3,}', '\n\n', t).strip()

def emit(src, dirp, ts, text):
    text = clean(text)
    if len(text) < 2 or NOISE.match(text):
        return
    if TASKBOOK.search(text[:400]):
        return
    day = datetime.datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d') if ts else ''
    out.write(json.dumps({"src": src, "dir": dirp[-40:], "d": day, "l": len(text),
                          "lang": lang(text), "text": text[:4000]}, ensure_ascii=False) + "\n")
    n[src] = n.get(src, 0) + 1

# --- opencode ---
con = sqlite3.connect('file:' + os.path.expanduser('~/.local/share/opencode/opencode.db') + '?mode=ro', uri=True)
rows = con.execute("""SELECT p.data, s.directory, m.time_created FROM part p
    JOIN message m ON m.id = p.message_id JOIN session s ON s.id = m.session_id
    WHERE json_extract(m.data,'$.role')='user' AND json_extract(p.data,'$.type')='text'""")
for (pdata, dirp, ts) in rows:
    try:
        t = json.loads(pdata).get("text") or ""
    except Exception:
        continue
    if not t.strip() or is_worktree(dirp):
        continue
    emit("opencode", (dirp or "").replace("\\", "/"), ts, t)
con.close()

# --- claude code jsonl ---
for fp in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    proj = os.path.basename(os.path.dirname(fp))
    for line in open(fp, encoding="utf-8", errors="replace"):
        if '"type":"user"' not in line and '"type": "user"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") != "user" or o.get("isMeta") or o.get("isSidechain"):
            continue
        m = o.get("message") or {}
        c = m.get("content")
        ts = None
        t0 = o.get("timestamp")
        if t0:
            ts = datetime.datetime.fromisoformat(t0.replace("Z", "+00:00")).timestamp() * 1000
        texts = []
        if isinstance(c, str):
            texts = [c]
        elif isinstance(c, list):
            texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        for t in texts:
            if t.strip():
                emit("claude", proj, ts, t)
out.close()
print("emitted:", n)
