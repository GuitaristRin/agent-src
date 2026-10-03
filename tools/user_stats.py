import json, os, re, random, collections

TMP = os.path.join(os.environ.get("TEMP", r"C:\Users\mc158\AppData\Local\Temp"), "opus-style")
recs = [json.loads(l) for l in open(os.path.join(TMP, "user_corpus.jsonl"), encoding="utf-8")]

print("总量:", len(recs), " 平均长度:", sum(r["l"] for r in recs)//len(recs))
buckets = collections.Counter()
for r in recs:
    b = "s<100" if r["l"] < 100 else "100-500" if r["l"] < 500 else ">=500"
    buckets[(r["src"], b)] += 1
for k in sorted(buckets):
    print(k, buckets[k])

PROF = re.compile(r'他妈|特么|tmd|卧槽|我操|操你|妈的|傻[比屄逼]|煞笔|牛魔|滚老木|滚犊|bar?\s?他妈|fuck|shit|damn|damn it', re.I)
LOAN = re.compile(r'\b(nein|ordinary|ridiculous|candidate|absurd|tough guy|whatever)\b', re.I)
WEN = re.compile(r'此致|实则|故而|乃[a-z\u4e00-\u9fff]|此为|综上|之必要|无疑|毫无疑问|费解|令人发笑|不堪')

for name, pat in [("粗口", PROF), ("外语插入", LOAN), ("文言/书面标记", WEN)]:
    hits = [r for r in recs if pat.search(r["text"])]
    chars = sum(len(pat.findall(r["text"])) for r in hits)
    print(f"{name}: {len(hits)} 条 ({len(hits)*100//len(recs)}%), 出现 {chars} 次")

# 样例展示命中的粗口上下文（脱敏展示前 40 字符窗口）
print("\n=== 粗口样本 ===")
seen = 0
for r in recs:
    m = PROF.search(r["text"])
    if m:
        s = max(0, m.start()-30)
        print(f"[{r['src']} {r['d']}] …{r['text'][s:m.end()+30]}…".replace("\n", " "))
        seen += 1
        if seen >= 12: break

print("\n=== 外语插入样本 ===")
for r in recs:
    m = LOAN.search(r["text"])
    if m:
        s = max(0, m.start()-40)
        print(f"[{r['src']} {r['d']}] …{r['text'][s:m.end()+40]}…".replace("\n", " "))

# 分层抽样
random.seed(11)
sel = [r for r in recs if r["src"] == "claude"]
pool = [r for r in recs if r["src"] == "opencode"]
sel += [r for r in pool if r["l"] >= 500][:60]
mid = [r for r in pool if 100 <= r["l"] < 500]
sel += random.sample(mid, min(60, len(mid)))
short = [r for r in pool if r["l"] < 100]
sel += random.sample(short, min(70, len(short)))
random.shuffle(sel)

fp = os.path.join(TMP, "sample_user.txt")
with open(fp, "w", encoding="utf-8") as f:
    for i, r in enumerate(sel):
        f.write(f"\n===== [{i}] {r['src']} {r['dir']} {r['d']} len={r['l']} =====\n{r['text'][:1500]}\n")
print("\nsampled:", len(sel), "->", fp)
