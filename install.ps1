<#
  talk2me installer for Windows PowerShell.

  Run it from the talk2me folder with:
      powershell -ExecutionPolicy Bypass -File .\install.ps1

  It will:
    1. check that Python 3 is installed
    2. install the dependencies (psutil, rich)
    3. add a `talk2me` command and a small history hook to your PowerShell profile

  Safe to run again: it replaces its own block in your profile instead of duplicating it.
#>

$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
$script = Join-Path $here "talk2me.py"
$reqs   = Join-Path $here "requirements.txt"

if (-not (Test-Path $script)) {
    Write-Host "Can't find talk2me.py next to install.ps1. Run this from the talk2me folder." -ForegroundColor Red
    exit 1
}

# 1. Python check
$pyOk = $false
try {
    $ver = & python --version 2>&1
    if ($LASTEXITCODE -eq 0 -and "$ver" -match "Python 3") { $pyOk = $true }
} catch { }
if (-not $pyOk) {
    Write-Host "Python 3 wasn't found." -ForegroundColor Red
    Write-Host "Install it with:  winget install Python.Python.3.12"
    Write-Host "Then CLOSE this window, open a new PowerShell, and run the installer again."
    exit 1
}
Write-Host "Found $ver"

# 2. Dependencies
Write-Host "Installing dependencies..."
& python -m pip install --quiet -r $reqs
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip failed. Try:  python -m pip install psutil rich" -ForegroundColor Red
    exit 1
}

# 3. Execution policy (PowerShell blocks profile scripts by default)
$eff = Get-ExecutionPolicy -Scope CurrentUser
if ($eff -eq "Undefined") { $eff = Get-ExecutionPolicy -Scope LocalMachine }
if ($eff -eq "Undefined") { $eff = "Restricted" }
if ($eff -in @("Restricted", "AllSigned")) {
    Write-Host ""
    Write-Host "PowerShell is set to '$eff', which stops your profile from loading." -ForegroundColor Yellow
    $answer = Read-Host "Set it to RemoteSigned for your user account only? [Y/n]"
    if ($answer -eq "" -or $answer -match "^[Yy]") {
        try {
            Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
            Write-Host "Done."
        } catch {
            Write-Host "Couldn't change it (maybe a company policy). talk2me won't load until it's allowed." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Skipped. talk2me won't load in new windows until profile scripts are allowed." -ForegroundColor Yellow
    }
}

# 4. Profile block
$block = @'
# ---- talk2me ----
function talk2me {
    $env:PYTHONUTF8 = "1"
    python "__T2M_PATH__" @args
}

# Logs each command's exit status so `talk2me last` and `talk2me why` work
if ($null -eq $global:__t2m_lastId) { $global:__t2m_lastId = 0 }
if (-not $global:__t2m_origPrompt) { $global:__t2m_origPrompt = $function:prompt }
function global:prompt {
    $ok   = $?
    $exit = $global:LASTEXITCODE
    $h = Get-History -Count 1
    if ($h -and $h.Id -ne $global:__t2m_lastId) {
        $global:__t2m_lastId = $h.Id
        $code = if ($ok) { 0 } elseif ($exit) { $exit } else { 1 }
        $cmd  = $h.CommandLine -replace "[\r\n]+", " "
        $ts   = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        [System.IO.File]::AppendAllText("$HOME\.talk2me_log", "$ts|$code|$cmd`n")
    }
    & $global:__t2m_origPrompt
}
# ---- end talk2me ----
'@
$block = $block.Replace("__T2M_PATH__", $script)

$profileDir = Split-Path $PROFILE
if (-not (Test-Path $profileDir)) { New-Item -ItemType Directory -Force $profileDir | Out-Null }

$content = ""
if (Test-Path $PROFILE) {
    $raw = Get-Content $PROFILE -Raw
    if ($raw) { $content = $raw }
}
# Remove any older talk2me block, then add the current one
$content = [regex]::Replace($content, "(?s)# ---- talk2me ----.*?# ---- end talk2me ----\r?\n?", "")
$newContent = ($content.TrimEnd() + "`r`n`r`n" + $block + "`r`n").TrimStart()
Set-Content -Path $PROFILE -Value $newContent -Encoding UTF8

Write-Host ""
Write-Host "talk2me is installed." -ForegroundColor Green
Write-Host "Close this window, open a new PowerShell, and type:  talk2me"