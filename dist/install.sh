#!/usr/bin/env bash
# echo 语气套壳安装脚本（macOS / Linux）
# 安装三样东西：ZCode 用户级 skill、ZCode 用户级 AGENTS.md 语气块、opencode agent。
# 可重复运行：skill/agent 直接覆盖，AGENTS.md 只更新 echo-voice 标记之间的块。
set -euo pipefail
DIST="$(cd "$(dirname "$0")" && pwd)"

# 1. ZCode skill
mkdir -p "$HOME/.zcode/skills"
rm -rf "$HOME/.zcode/skills/echo"
cp -r "$DIST/skills/echo" "$HOME/.zcode/skills/echo"
echo "installed: $HOME/.zcode/skills/echo/SKILL.md"

# 2. opencode agents（没装 opencode 就跳过）
if command -v opencode >/dev/null 2>&1; then
    mkdir -p "$HOME/.config/opencode/agents"
    cp "$DIST/opencode/echo.md" "$HOME/.config/opencode/agents/echo.md"
    echo "installed: $HOME/.config/opencode/agents/echo.md"
    cp "$DIST/opencode/critic.md" "$HOME/.config/opencode/agents/critic.md"
    echo "installed: $HOME/.config/opencode/agents/critic.md"
else
    echo "skipped: opencode not found"
fi

# 3. ZCode 用户级 AGENTS.md（存在则原地更新标记块，不存在则新建）
AGENTS="$HOME/.zcode/AGENTS.md"
if ! command -v python3 >/dev/null 2>&1; then
    echo "warning: python3 缺失，跳过 AGENTS.md 自动更新；请手动把 AGENTS-block.md 合并进 $AGENTS"
elif [ -f "$AGENTS" ] && grep -q '<!-- echo-voice:start -->' "$AGENTS"; then
    python3 - "$AGENTS" "$DIST/AGENTS-block.md" <<'PY'
import re, sys
agents_path, block_path = sys.argv[1], sys.argv[2]
block = open(block_path, encoding="utf-8").read().rstrip("\n")
s = open(agents_path, encoding="utf-8").read()
s = re.sub(r"<!-- echo-voice:start -->.*?<!-- echo-voice:end -->", lambda m: block, s, flags=re.S)
open(agents_path, "w", encoding="utf-8").write(s)
PY
    echo "updated: $AGENTS (echo-voice block replaced)"
elif [ -f "$AGENTS" ]; then
    printf '\n%s\n' "$(cat "$DIST/AGENTS-block.md")" >> "$AGENTS"
    echo "appended: $AGENTS (echo-voice block added)"
else
    printf '# 个人默认指令\n\n%s\n' "$(cat "$DIST/AGENTS-block.md")" > "$AGENTS"
    echo "created: $AGENTS"
fi

echo ""
echo "验证：新开 ZCode 会话即生效；opencode 用 'opencode agent list' 应看到 echo。"
