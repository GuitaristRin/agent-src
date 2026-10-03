# echo 语气套壳安装脚本（Windows）
# 安装三样东西：ZCode 用户级 skill、ZCode 用户级 AGENTS.md 语气块、opencode agent。
# 可重复运行：skill/agent 直接覆盖，AGENTS.md 只更新 echo-voice 标记之间的块。
$ErrorActionPreference = "Stop"
$dist = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. ZCode skill
New-Item -ItemType Directory -Force -Path "$HOME\.zcode\skills" | Out-Null
if (Test-Path "$HOME\.zcode\skills\echo") { Remove-Item -Recurse -Force "$HOME\.zcode\skills\echo" }
Copy-Item -Recurse "$dist\skills\echo" "$HOME\.zcode\skills\echo"
Write-Host "installed: $HOME\.zcode\skills\echo\SKILL.md"

# 2. opencode agent（没装 opencode 就跳过）
if (Get-Command opencode -ErrorAction SilentlyContinue) {
    $ocDir = "$HOME\.config\opencode\agents"
    New-Item -ItemType Directory -Force -Path $ocDir | Out-Null
    Copy-Item -Force "$dist\opencode\echo.md" "$ocDir\echo.md"
    Write-Host "installed: $ocDir\echo.md"
} else {
    Write-Host "skipped: opencode not found"
}

# 3. ZCode 用户级 AGENTS.md（存在则原地更新标记块，不存在则新建）
$agents = "$HOME\.zcode\AGENTS.md"
$utf8 = New-Object System.Text.UTF8Encoding($false)
$block = [System.IO.File]::ReadAllText("$dist\AGENTS-block.md", [System.Text.Encoding]::UTF8).TrimEnd()
if (Test-Path $agents) {
    $content = [System.IO.File]::ReadAllText($agents, [System.Text.Encoding]::UTF8)
    if ($content -match '(?s)<!-- echo-voice:start -->.*?<!-- echo-voice:end -->') {
        $content = [regex]::Replace($content, '(?s)<!-- echo-voice:start -->.*?<!-- echo-voice:end -->', { param($m) $block })
        [System.IO.File]::WriteAllText($agents, $content, $utf8)
        Write-Host "updated: $agents (echo-voice block replaced)"
    } else {
        [System.IO.File]::WriteAllText($agents, [System.IO.File]::ReadAllText($agents, [System.Text.Encoding]::UTF8) + "`n$block`n", $utf8)
        Write-Host "appended: $agents (echo-voice block added)"
    }
} else {
    [System.IO.File]::WriteAllText($agents, "# 个人默认指令`n`n$block`n", $utf8)
    Write-Host "created: $agents"
}

Write-Host "`n验证：新开 ZCode 会话即生效；opencode 用 'opencode agent list' 应看到 echo。"
