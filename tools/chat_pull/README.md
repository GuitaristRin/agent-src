# chat_pull · 微信/QQ 本人消息抽取

目标：把**指定群聊、本人账号、纯文本**的消息落成仓库外的 txt，喂给语体分析。四条契约：

1. **原文不入库**——输出目录必须在 agent-src 仓库之外，脚本强制校验，违者拒绝运行；
2. 只保留本人账号发出的消息（他人消息连存档都不进）；
3. 只保留纯文本（图片/语音/视频/系统消息/引用块剥掉）；
4. 导出前脱敏（手机号/证件号/长数字串/密码字段），且保留 burst 分界——连发消息的空行是语体结构特征，不许抹平。

## 用哪条路（按你的微信/QQ 版本对号入座）

| 情况 | 路径 | 说明 |
|---|---|---|
| 微信 3.9.x | 装开源工具导出 CSV → 配置 `export_roots` | 留痕（MemoTrace）/ PyWxDump 都能把本机加密库解密后导出 CSV，含 IsSender 字段 |
| 微信 4.0 | 用支持 4.0 的导出工具（如 wechat-dump-rs 系）→ 同上 | 4.0 换了存储结构，工具生态变化快，先用工具导出，别指望本脚本直接啃 4.0 原库 |
| QQ NT | 先用开源 NT 库解密方案得到可读 `nt_msg.db` → 配置 `decrypted_dbs` | 列名拿不准就先跑 `python chat_pull.py --inspect <db路径>`，把输出发我，我补适配 |
| 手头只有聊天窗口 | **多选→复制→存成 txt** 丢进 `输出目录/manual/` | 适配层 D：按「发送者名 + 时间戳」头行认领本人消息。你自己只会选中自己的消息的话，`own_names` 直接命中 |

解密工具是灰色地带且追版本：**用哪个、要不要用，你拍板**；本脚本只负责解密之后的过滤与导出，不碰加密层。

## 配置（`chat_pull.toml`）

- `[output].dir`：导出目录，默认 `~/Documents/chat-corpus`（仓库外）；
- `own_names`：微信/QQ 里你的昵称（手动路径认领用）；
- `[wechat].export_roots / decrypted_dbs / groups / start_date / end_date`；
- `[qq].decrypted_dbs / own_uin / groups`。

## 运行

```bash
python tools/chat_pull/chat_pull.py --config tools/chat_pull/chat_pull.toml
python tools/chat_pull/chat_pull.py --inspect "C:/path/to/nt_msg.db"   # 看表结构
```

输出：`<output>/<平台>_<群名>.txt`，格式为 burst 分段（段间空行，段内每条一行，段首带时间戳），外加脱敏。统计与特征化是下一步（进 user-voice 配方时另行执行）。
