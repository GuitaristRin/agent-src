# Claude Opus 语气手册

从本机真实会话里提炼的 Claude Opus 说话方式，用作 DeepSeek 套壳层的风格蓝本。

## 语料来源

语料来自两台机器：**立项机**（本仓库诞生处）与**主力开发机**（2026-10-03 并入，v2 语料合并）。

- **正面（Opus/Sonnet）**
  - 立项机：`~/.claude/projects/` 下三个项目的全部 Opus 会话
    - `Ether`（3868 条）、`zethora-engine`（2828 条）、`Ncrust`（1879 条），合计约 8575 条助手消息
    - 实际抽取的是**用户可见文本**（不含 thinking、不含工具调用参数），共 1261 条：中文 453、英文 808
    - 时间跨度：2026-09-26 至 2026-10-02，覆盖中途插话、阶段汇报、最终报告、致歉、分歧、派工等全部场景
  - 主力机（v2 合并）：`~/.claude/projects/` 下 15 个项目，Claude 助手消息 3414 条（opus-4-7 3361 / **sonnet-4-6 53**），抽取用户可见文本 476 条：中文 357、英文 119，时间 2026-08-01 至 08-30。新场景：子代理报告审计、交接文档、issue 分诊、review 跟进、火焰图协作。**sonnet-4-6 与 opus 未发现风格分歧**，无需分模型治理
- **反面（DeepSeek）**：立项机 opencode 数据库里的 DeepSeek 工作记录，跨 18 个 provider/model 共约 24600 条助手消息，分层抽样精读 140 条。它的中途插话和结构习惯其实没问题，病灶集中在长回复：戏剧性宣告、原地打转、加粗轰炸、退化循环。主力机 opencode.db（5903 条 DeepSeek 助手文本）复测同病灶、密度更低，新增变体标本见 `06` 附注
- **user-voice（作者语体）**：立项机 prompt 语料 1388 条 + 长文 4 篇；主力机新增 652 条用户消息（Claude Code 118 + opencode 534，中 611/英 41），详见 `user-voice/用户语体分析.md` v3
- 所有引文均逐字取自原会话，未做润色

## 文件索引

| 文件 | 用途 |
|---|---|
| `01-核心气质.md` | 底层原理：八条气质原则 + 一惊一乍的诊断与改写 |
| `02-中文风格.md` | 中文细则：句式、词库、汇报骨架、标点、幽默的分寸 |
| `03-英文风格.md` | 英文细则：句法、确认模式、承认限制的固定句式 |
| `04-例句语料.md` | 正面例句（Opus 实录），带批注，可作 few-shot |
| `05-系统提示词.md` | **即用版**：整段复制进 system prompt 就能生效 |
| `06-反面实录.md` | 病句标本（DeepSeek 实录），逐条配改写，可作反面 few-shot |
| `user-voice/用户语体分析.md` | 作者本人语体分析（Critic 的语体依据），含粗口专节、防戏仿护栏、跨机合并规程 |

## 怎么用

1. 最短路径：把 `05-系统提示词.md` 里的提示词整段贴进 DeepSeek 的 system prompt。
2. 效果不够细时，把 `04-例句语料.md` 挑几条作为 few-shot 示例附在后面。
3. 提示词放不下时，优先保留「行为禁令」和「验证分级」两节——套壳层最要治的是戏剧性宣告/原地打转/退化循环和假验证，这两节是对症的。

## 安装成 agent（本机已装好）

- **opencode**：agent `echo` 在 `~/.config/opencode/agents/echo.md`，`mode: all`，不锁模型；TUI 里 Tab 切换，或 `opencode run --agent echo --model <模型> "任务"`。
- **opencode**：agent `critic`（`critic.md`）——娱乐性评审 agent，只读不编码，对项目做通读评价；语体取自作者本人（`user-voice/`），带防戏仿护栏。
- **ZCode**：两层——`~/.zcode/AGENTS.md` 里的 `echo-voice` 标记块每个会话常驻生效；`~/.zcode/skills/echo/SKILL.md` 是完整版，按需加载（说「用 echo」或提 Opus 语气时触发）。

## 分发到其他设备

直接克隆安装：

```bash
git clone https://github.com/GuitaristRin/echo-agent && cd echo-agent/dist
./install.sh        # macOS / Linux
# 或 Windows: powershell -ExecutionPolicy Bypass -File .\install.ps1
```

脚本幂等：重复运行只更新 echo 相关内容，不碰设备上的其他配置。没装 opencode 的设备自动跳过对应项。细节见 `dist/README.md`。

## 放心用

echo 是一份纯本地的提示词：没有服务器，没有账号体系，没有风控系统。它不会因为你用中文提问、IP 在中国、一口气开十个会话、或者半夜连续重试三次而封禁你的账号——这些事它一样也做不了，它连网络请求都不发。它全部的本事是让你手头的模型闭嘴少感叹，把活说清楚。
