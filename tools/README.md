# tools · 语料抽取与分析脚本

手册里所有数字的产证流程。2026-10-03 在本机（Windows）运行，输出落在 `%TEMP%/opus-style/`。

## 流水线与产物对应

| 脚本 | 输入 | 产物 | 支撑的手册数字 |
|---|---|---|---|
| `extract.py` | `~/.claude/projects/*/*.jsonl`（assistant 消息的 text 块） | `opus_all.jsonl`（1261 条：zh 453 / en 808） | README「8575 条助手消息、抽取 1261 条」 |
| `extract_ds.py` | `~/.local/share/opencode/opencode.db`（assistant text parts，provider/model 含 deepseek） | `ds_all.jsonl`（9900 条 text parts，跨 18 组 provider/model） | README「24600 条 DeepSeek 消息」 |
| `extract_user.py` | 上两者的 user 侧（opencode 1290 + claude 98） | `user_corpus.jsonl`（1388 条） | 用户语体分析的语料量；worker 过滤规则写在脚本内（worktree 目录 + 任务书格式双过滤） |
| `user_stats.py` | `user_corpus.jsonl` | 特征统计 + `sample_user.txt` | 粗口 1.7%（24 条/34 处）、外语插入、文言标记 0.6%、五类定义式句型零命中 |
| `token_stats.py` | `opus_all.jsonl` + `ds_all.jsonl` | 打转/退化/虚构对话统计 | DS 打转消息 70 条占 10.2%、虚构对话 10 条、Opus 同类为零 |

## 运行前提

- Python 3.10+；`extract_ds.py`/`extract_user.py` 需要 opencode 的 SQLite 库（只读连接）。
- 路径假设写死在本机布局上（`~/.claude/projects`、`~/.local/share/opencode/opencode.db`），换机器先改脚本头部。
- 语言判定阈值：CJK 占比 ≥0.15 记为 zh。这是粗分类，样本的人工核对比例见各手册。

## 已知局限

- `extract_ds.py` 的 provider 名含 deepseek 但模型是 GPT 的组合（deepseek2-copy/gpt-5.6-sol）靠 `user_stats.py` 里的 `"gpt" not in model` 二次过滤。
- 抽样是分层的（长/中/短按比例），非全量精读；全量统计与人工精读的交叉核对记录在 `user-voice/用户语体分析.md`。
- 手册中引用的原话均可在 jsonl 产物中按日期与模型字段回查。
