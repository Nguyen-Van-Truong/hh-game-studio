#Requires -Version 5.1
<#
.SYNOPSIS
    Codex WM 模型一键配置工具
.DESCRIPTION
    自动完成 gpt-5.6-sol-wm 模型的启用流程：
      1. 定位 CODEX_HOME 与最新版 codex CLI
      2. 检查本地模型缓存中是否存在 WM 条目
      3. 先运行最小探针，确认服务器端账号权限（核心步骤）
      4. 权限通过后才生成自定义模型目录并修改 config.toml
    支持 -Rollback 一键回滚。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File Enable-CodexWM.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File Enable-CodexWM.ps1 -Rollback
#>
[CmdletBinding()]
param(
    [string]$CodexHome,
    [switch]$Rollback,
    [switch]$SkipProbe
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 控制台统一用 UTF-8，避免中文乱码、正确解码原生命令输出
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [Text.Encoding]::UTF8

$WM_SLUG   = 'gpt-5.6-sol-wm'
$AUTO_SLUG = 'codex-auto-review'

function Write-Step([string]$Msg) { Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Ok([string]$Msg)   { Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Write-Warn([string]$Msg) { Write-Host "  [!!] $Msg" -ForegroundColor Yellow }
function Write-Fail([string]$Msg) { Write-Host "`n[失败] $Msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# 0. 定位 CODEX_HOME
# ---------------------------------------------------------------------------
if (-not $CodexHome) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
}
$CachePath   = Join-Path $CodexHome 'models_cache.json'
$CatalogPath = Join-Path $CodexHome 'models_wm_visible.json'
$ConfigPath  = Join-Path $CodexHome 'config.toml'

if (-not (Test-Path -LiteralPath $CodexHome)) {
    Write-Fail "找不到 CODEX_HOME：$CodexHome`n请先安装并登录 Codex。"
}
Write-Step "CODEX_HOME = $CodexHome"

# ---------------------------------------------------------------------------
# 回滚模式
# ---------------------------------------------------------------------------
if ($Rollback) {
    Write-Step '回滚 config.toml'
    if (-not (Test-Path -LiteralPath $ConfigPath)) { Write-Fail "config.toml 不存在：$ConfigPath" }

    # 从最早的备份里取回 WM 配置前的 model / model_reasoning_effort
    # （用最早而不是最新：重复运行脚本时新备份里可能已经是 WM 配置）
    $oldModel = $null; $oldEffort = $null
    $bak = Get-ChildItem -LiteralPath $CodexHome -Filter 'config.toml.before-wm-*.bak' |
           Sort-Object LastWriteTime | Select-Object -First 1
    if ($bak) {
        foreach ($line in Get-Content -LiteralPath $bak.FullName) {
            if ($line -match '^\s*\[') { break }  # 只看顶层
            if (-not $oldModel  -and $line -match '^\s*model\s*=\s*"(.+)"')                   { $oldModel  = $Matches[1] }
            if (-not $oldEffort -and $line -match '^\s*model_reasoning_effort\s*=\s*"(.+)"')  { $oldEffort = $Matches[1] }
        }
        Write-Ok "参考备份：$($bak.Name)（model = $oldModel）"
    } else {
        Write-Warn '没有找到配置备份，将直接删除 WM 相关行。'
    }

    $lines = [System.Collections.Generic.List[string]]@()
    if (Test-Path -LiteralPath $ConfigPath) { $lines.AddRange([string[]](Get-Content -LiteralPath $ConfigPath)) }

    $sectionIdx = $lines.Count
    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\s*\[') { $sectionIdx = $i; break } }

    for ($i = $sectionIdx - 1; $i -ge 0; $i--) {
        if ($lines[$i] -match '^\s*model_catalog_json\s*=') { $lines.RemoveAt($i); $sectionIdx-- }
        elseif ($lines[$i] -match '^\s*model\s*=') {
            if ($oldModel) { $lines[$i] = "model = `"$oldModel`"" } else { $lines.RemoveAt($i); $sectionIdx-- }
        }
        elseif ($lines[$i] -match '^\s*model_reasoning_effort\s*=') {
            if ($oldEffort) { $lines[$i] = "model_reasoning_effort = `"$oldEffort`"" } else { $lines.RemoveAt($i); $sectionIdx-- }
        }
    }
    [IO.File]::WriteAllText($ConfigPath, ($lines -join "`r`n") + "`r`n", [Text.UTF8Encoding]::new($false))
    Write-Ok 'config.toml 已回滚（自定义目录文件保留备查，可手动删除）'
    Write-Host "`n请彻底退出并重启 Codex 使配置生效。" -ForegroundColor Cyan
    exit 0
}

# ---------------------------------------------------------------------------
# 1. 找到最新版本的 codex CLI
# ---------------------------------------------------------------------------
Write-Step '查找 codex CLI（自动选用最新版本）'
$candidates = [System.Collections.Generic.List[string]]@()
$cmd = Get-Command codex -ErrorAction SilentlyContinue
if ($cmd) { $candidates.Add($cmd.Source) }
if ($env:LOCALAPPDATA) {
    Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin\*\codex.exe') -ErrorAction SilentlyContinue |
        ForEach-Object { $candidates.Add($_.FullName) }
}
if ($candidates.Count -eq 0) { Write-Fail '找不到 codex 命令。请先安装 Codex CLI 或桌面版。' }

$best = $null; $bestVer = [version]'0.0.0'
foreach ($bin in ($candidates | Select-Object -Unique)) {
    try {
        $vOut = (& $bin --version 2>$null | Select-Object -First 1)
        if ($vOut -match '(\d+\.\d+\.\d+)') {
            $v = [version]$Matches[1]
            Write-Host "  发现 $bin  (v$v)"
            if ($v -gt $bestVer) { $bestVer = $v; $best = $bin }
        }
    } catch { }
}
if (-not $best) { Write-Fail '找到 codex 但无法解析版本号。' }
$CodexBin = $best
Write-Ok "使用 v$bestVer ：$CodexBin"

# ---------------------------------------------------------------------------
# 2. 检查模型缓存中的 WM 条目
# ---------------------------------------------------------------------------
Write-Step '检查模型缓存'
if (-not (Test-Path -LiteralPath $CachePath)) {
    Write-Fail "找不到 models_cache.json。请先正常启动一次 Codex 让它生成缓存，再重新运行本脚本。"
}
$cacheRaw = [IO.File]::ReadAllText($CachePath)
if ($cacheRaw -notmatch [regex]::Escape("`"slug`": `"$WM_SLUG`"") -and $cacheRaw -notmatch '"slug"\s*:\s*"gpt-5\.6-sol-wm"') {
    Write-Fail "缓存中没有 $WM_SLUG 条目。请先启动一次 Codex 刷新缓存后再试。"
}
Write-Ok "缓存中已存在 $WM_SLUG 条目"

# ---------------------------------------------------------------------------
# 3. 服务器权限探针（先验证权限，再动本地配置）
# ---------------------------------------------------------------------------
if (-not $SkipProbe) {
    Write-Step '运行服务器权限探针（约 10-60 秒）'
    $probeArgs = @(
        '--ask-for-approval', 'never', 'exec',
        '--ignore-user-config', '--ephemeral', '--json', '--skip-git-repo-check',
        '-C', $env:TEMP,
        '--sandbox', 'read-only',
        '--model', $WM_SLUG,
        '-c', 'model_reasoning_effort="low"',
        '-c', 'approval_policy="never"',
        '-c', 'web_search="disabled"',
        '-c', 'project_doc_max_bytes=0',
        'Reply exactly WM_OK. Do not call any tool.'
    )
    # PS 5.1 下原生命令的 stderr 经 2>&1 会触发 NativeCommandError，临时放宽
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $probeOut = ('' | & $CodexBin @probeArgs 2>&1 | Out-String)
    $ErrorActionPreference = $prevEAP

    if ($probeOut -match 'WM_OK') {
        Write-Ok '服务器返回 WM_OK —— 你的账号有权限调用该模型'
    }
    elseif ($probeOut -match 'model is not supported') {
        Write-Fail "服务器拒绝：model is not supported。`n你的账号（大概率是 Free 方案）没有该模型权限，本地怎么改都没用。`n需要 Plus / Pro / Team 任意付费方案。"
    }
    elseif ($probeOut -match 'requires a newer version') {
        Write-Fail "服务器要求更新版本的 Codex。当前最新可用 CLI 为 v$bestVer，请升级 Codex 后重试。"
    }
    elseif ($probeOut -match '401|Unauthorized|unauthorized') {
        Write-Fail '登录已过期（401）。请运行 codex login 重新登录后再试。'
    }
    else {
        Write-Warn '探针返回了无法识别的结果，原始输出如下：'
        Write-Host $probeOut
        Write-Fail '无法确认账号权限，为安全起见已中止。可加 -SkipProbe 强制继续（不推荐）。'
    }
} else {
    Write-Warn '已跳过权限探针（-SkipProbe）'
}

# ---------------------------------------------------------------------------
# 4. 备份 + 生成 WM 可见目录（只改 WM 的 visibility）
# ---------------------------------------------------------------------------
Write-Step '生成自定义模型目录'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item -LiteralPath $CachePath -Destination (Join-Path $CodexHome "models_cache.before-wm-$stamp.bak")
if (Test-Path -LiteralPath $CatalogPath) {
    Copy-Item -LiteralPath $CatalogPath -Destination "$CatalogPath.before-$stamp.bak"
}
Copy-Item -LiteralPath $CachePath -Destination $CatalogPath -Force

$raw     = [IO.File]::ReadAllText($CatalogPath)
$pattern = '(?s)("slug"\s*:\s*"gpt-5\.6-sol-wm".*?"visibility"\s*:\s*)"hide"'
$m       = [regex]::Matches($raw, $pattern)
if ($m.Count -ne 1) { Write-Fail "预期精确匹配 1 个隐藏 WM 条目，实际 $($m.Count) 个，已中止。" }
$updated = [regex]::new($pattern).Replace($raw, { param($x) $x.Groups[1].Value + '"list"' }, 1)
[IO.File]::WriteAllText($CatalogPath, $updated, [Text.UTF8Encoding]::new($false))

# 校验：只动了 WM，其他模型不受影响（按条目边界截取，避免跨条目误匹配）
$verifyRaw = [IO.File]::ReadAllText($CatalogPath)
function Get-ModelBlock([string]$Raw, [string]$Slug) {
    $idx = $Raw.IndexOf("`"$Slug`"")
    if ($idx -lt 0) { return $null }
    $next = $Raw.IndexOf('"slug"', $idx + 1)
    if ($next -gt 0) { return $Raw.Substring($idx, $next - $idx) }
    return $Raw.Substring($idx)
}
$wmBlock   = Get-ModelBlock $verifyRaw $WM_SLUG
$autoBlock = Get-ModelBlock $verifyRaw $AUTO_SLUG
if (-not $wmBlock -or $wmBlock -notmatch '"visibility"\s*:\s*"list"') {
    Write-Fail '目录校验失败：WM 条目未正确设为 list。'
}
if ($autoBlock -and $autoBlock -notmatch '"visibility"\s*:\s*"hide"') {
    Write-Fail '目录校验失败：codex-auto-review 条目状态异常。'
}
Write-Ok "${CatalogPath}（WM: hide -> list，其余模型未动）"

# ---------------------------------------------------------------------------
# 5. 更新 config.toml（幂等：存在则替换，不存在则插入顶层）
# ---------------------------------------------------------------------------
Write-Step '更新 config.toml'
if (Test-Path -LiteralPath $ConfigPath) {
    Copy-Item -LiteralPath $ConfigPath -Destination (Join-Path $CodexHome "config.toml.before-wm-$stamp.bak")
    $lines = [System.Collections.Generic.List[string]]@()
    $lines.AddRange([string[]](Get-Content -LiteralPath $ConfigPath))
} else {
    $lines = [System.Collections.Generic.List[string]]@()
}

$tomlCatalogPath = $CatalogPath -replace '\\', '/'
$kv = @(
    @('model', $WM_SLUG),
    @('model_catalog_json', $tomlCatalogPath),
    @('model_reasoning_effort', 'max')
)
$sectionIdx = $lines.Count
for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\s*\[') { $sectionIdx = $i; break } }
foreach ($pair in $kv) {
    $key = $pair[0]; $val = $pair[1]; $done = $false
    for ($i = 0; $i -lt $sectionIdx; $i++) {
        if ($lines[$i] -match ("^\s*" + [regex]::Escape($key) + "\s*=")) {
            $lines[$i] = "$key = `"$val`""; $done = $true; break
        }
    }
    if (-not $done) { $lines.Insert($sectionIdx, "$key = `"$val`""); $sectionIdx++ }
}
[IO.File]::WriteAllText($ConfigPath, ($lines -join "`r`n") + "`r`n", [Text.UTF8Encoding]::new($false))
Write-Ok "config.toml 已写入：model = $WM_SLUG / reasoning = max"

# ---------------------------------------------------------------------------
# 6. 收尾
# ---------------------------------------------------------------------------
$running = Get-Process -Name 'codex' -ErrorAction SilentlyContinue
Write-Host "`n========================================" -ForegroundColor Green
Write-Host ' 配置完成！' -ForegroundColor Green
Write-Host '========================================' -ForegroundColor Green
if ($running) { Write-Warn '检测到 Codex 正在运行。' }
Write-Host '下一步：从系统托盘彻底退出 Codex，再重新打开。' -ForegroundColor Cyan
Write-Host '回滚：  powershell -ExecutionPolicy Bypass -File Enable-CodexWM.ps1 -Rollback'
