# dist · echo 语气套壳分发包

把这个包（连同上级目录的 01–06 手册一起）拷到 U 盘 / 网盘 / git 仓库，在任何设备上运行对应安装脚本即可。

## 包内容

| 文件 | 去向 | 作用 |
|---|---|---|
| `skills/echo/SKILL.md` | `~/.zcode/skills/echo/` | ZCode 按需加载的完整语气规则（说「用 echo」或触发关键词时生效） |
| `AGENTS-block.md` | 合并进 `~/.zcode/AGENTS.md` | ZCode 每个会话**常驻**的语气核心（真正的"套壳"层） |
| `opencode/echo.md` | `~/.config/opencode/agents/echo.md` | opencode 的 `echo` agent（不锁模型，TUI 里 Tab 切换） |
| `install.ps1` | — | Windows 上一键安装以上三样 |
| `install.sh` | — | macOS / Linux 上一键安装以上三样 |

## 安装（其他设备）

```powershell
# Windows：进入 dist 目录后
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

```bash
# macOS / Linux：
chmod +x install.sh && ./install.sh
```

脚本行为：skill 和 agent 直接覆盖更新；`~/.zcode/AGENTS.md` 不存在就新建、已有内容就把 `<!-- echo-voice -->` 标记块原地更新或追加，**不碰标记之外的内容**。没装 opencode 的设备自动跳过那一项。

## 验证

- **ZCode**：新开会话，让它「汇报一下你刚做完的任务」，看是否结论先行、无感叹号、有验证分级。也可以在 设置 → Skills 里确认 `echo` 已被发现。
- **opencode**：`opencode agent list` 应出现 `echo (all)`；跑一句 `opencode run --agent echo --model <你的模型> "自检：汇报一个刚修好的 bug"`。

## 卸载

- ZCode：删 `~/.zcode/skills/echo/`，再从 `~/.zcode/AGENTS.md` 删掉 `<!-- echo-voice:start -->` 到 `<!-- echo-voice:end -->` 之间的块。
- opencode：删 `~/.config/opencode/agents/echo.md`。

## 可选：跨工具共用

`skills/echo/` 同时复制到 `~/.agents/skills/echo/` 的话，Claude Code、Codex 等同样读 `~/.agents` 的工具也能用这个 skill。ZCode 的读取优先级是 `~/.zcode/skills` 高于 `~/.agents/skills`，两处都放不冲突。

## 修改流程

规则要改的时候：先改本包里的 `AGENTS-block.md` / `skills/echo/SKILL.md` / `opencode/echo.md`，再在每台设备重跑安装脚本。手册 01–06 是规则的推导依据，改规则前先看 06 里有没有新标本。
