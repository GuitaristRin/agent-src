import json, os, re, statistics, collections

TMP = os.path.join(os.environ.get("TEMP", r"C:\Users\mc158\AppData\Local\Temp"), "opus-style")

def load(name, model_filter=None):
    recs = []
    for l in open(os.path.join(TMP, name), encoding="utf-8"):
        r = json.loads(l)
        if model_filter and not model_filter(r): continue
        recs.append(r["text"])
    return recs

ds = load("ds_all.jsonl", lambda r: "gpt" not in r["m"].lower())
opus = load("opus_all.jsonl")

def stats(name, texts):
    ls = [len(t) for t in texts]
    ls.sort()
    n = len(ls)
    print(f"{name}: n={n}, mean={statistics.mean(ls):.0f} chars, median={ls[n//2]}, p90={ls[int(n*0.9)]}, total={sum(ls)/10000:.1f}万字符")

stats("DS  visible", ds)
stats("Opus visible", opus)

# degenerate / dithering heuristics on DS
pat_loop = re.compile(r'^(run|ok|执行|马上|好。?|user[:：])\s*$', re.I | re.M)
dith = re.compile(r'(let me reconsider|let me step back|let me think|actually[ ,—-]+let me|wait[ ,—]+actually|我(们)?(重新|再)?(考虑|想想)|让我(重新|换个|退一步))', re.I)

waste_loop = [t for t in ds if len(pat_loop.findall(t)) >= 6]
waste_dith = [t for t in ds if len(dith.findall(t)) >= 4]
print(f"\nDS 退化循环消息(≥6次 Run/OK/执行): {len(waste_loop)} 条, 共 {sum(len(t) for t in waste_loop)/10000:.2f}万字符")
print(f"DS 打转消息(≥4次 let me reconsider/让我重新): {len(waste_dith)} 条, 共 {sum(len(t) for t in waste_dith)/10000:.2f}万字符")

# opus equivalent for comparison
waste_dith_o = [t for t in opus if len(dith.findall(t)) >= 4]
waste_loop_o = [t for t in opus if len(pat_loop.findall(t)) >= 6]
print(f"Opus 同类退化消息: loop={len(waste_loop_o)}, dither={len(waste_dith_o)}")

# fake dialogue marker
fake = [t for t in ds if re.search(r'user[:：]\s*(run|go|执行|快速)', t, re.I)]
print(f"DS 虚构对话(User: run)消息: {len(fake)} 条, 共 {sum(len(t) for t in fake)/10000:.2f}万字符")
