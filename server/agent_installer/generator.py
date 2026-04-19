"""
HopMap agent installer — PowerShell script generator.

Produces a self-contained .ps1 that a parent can hand to the child's PC.
The script runs once as Administrator and handles the full setup:
  Python, Tesseract OCR, agent files, pip packages, Task Scheduler auto-start.
"""

from __future__ import annotations

# Pinned Tesseract 5.x release — update URL and hash when bumping the version.
_TESSERACT_URL = (
    "https://github.com/UB-Mannheim/tesseract/releases/download/"
    "v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
)
_TESSERACT_SHA256 = "C885FFF6998E0608BA4BB8AB51436E1C6775C2BAFC2559A19B423E18678B60C9"

# Agent source files that the installer downloads from the server.
_AGENT_FILES = ["agent.py", "config.py", "requirements.txt"]

# How long a setup code is valid after GET /agent/installer issues it.
_SETUP_CODE_TTL_HOURS = 1

_INSTALL_DIR = "C:\\HopMap"


def build_uninstaller(*, child_name: str) -> str:
    """Return a PowerShell uninstaller script that cleanly removes the agent."""
    safe_name = "".join(c for c in child_name if c.isalnum() or c == " ").strip() or "child"

    return f"""\
<#
.SYNOPSIS
    HopMap agent uninstaller for {safe_name}.
.DESCRIPTION
    Stops the running agent, removes the scheduled task, and deletes all files.
    Right-click and choose "Run with PowerShell" - the script requests elevation automatically.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
trap {{ Write-Host ""; Write-Host "  [!] Unexpected error: $_" -ForegroundColor Red; $null = Read-Host "  Press Enter to close"; exit 1 }}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# -- Self-elevation -----------------------------------------------------------
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    Start-Process PowerShell -Verb RunAs -WindowStyle Normal `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    [System.Environment]::Exit(0)
}}

$TaskName  = "HopMap - {safe_name}"
$InstallDir = '{_INSTALL_DIR}'

Write-Host ""
Write-Host "  HopMap Agent Uninstaller" -ForegroundColor White
Write-Host "  -----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# -- 1. Stop and remove scheduled task ----------------------------------------
Write-Host "  [*] Stopping scheduled task..." -ForegroundColor Cyan
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "  [+] Scheduled task removed." -ForegroundColor Green

# -- 2. Kill any running agent process ----------------------------------------
Write-Host "  [*] Stopping agent process..." -ForegroundColor Cyan
Get-WmiObject Win32_Process | Where-Object {{ $_.CommandLine -like "*agent.py*" }} | ForEach-Object {{
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}}
Write-Host "  [+] Agent process stopped." -ForegroundColor Green

# -- 3. Remove install directory ----------------------------------------------
Write-Host "  [*] Removing files..." -ForegroundColor Cyan
if (Test-Path $InstallDir) {{
    Remove-Item -Path $InstallDir -Recurse -Force
    Write-Host "  [+] $InstallDir removed." -ForegroundColor Green
}} else {{
    Write-Host "  [+] $InstallDir already gone." -ForegroundColor Green
}}

# -- Done ---------------------------------------------------------------------
Write-Host ""
Write-Host "  [OK] HopMap agent removed successfully for {safe_name}." -ForegroundColor Green
Write-Host ""
$null = Read-Host "  Press Enter to close"
"""


def build_readme(*, child_name: str, ttl_hours: int = 1) -> str:
    """Return a plain-text README for the installer ZIP."""
    safe_name = "".join(c for c in child_name if c.isalnum() or c == " ").strip() or "child"

    return f"""\
HopMap Agent Setup - {safe_name}
{"=" * (len("HopMap Agent Setup - ") + len(safe_name))}

FILES IN THIS PACKAGE
---------------------
  hopmap_install.ps1    Run this ONCE on {safe_name}'s PC to install the HopMap agent.
  hopmap_uninstall.ps1  Run this to completely remove the agent from the PC.
  README.txt            This file.


HOW TO INSTALL
--------------
1. Copy this folder to {safe_name}'s PC (USB drive, shared folder, etc.)
2. Right-click "hopmap_install.ps1" and choose "Run with PowerShell"
3. Click "Yes" when Windows asks for administrator permission
4. The script installs everything automatically and starts the agent immediately
5. The agent will also start automatically every time {safe_name} logs in


HOW TO UNINSTALL
----------------
1. Right-click "hopmap_uninstall.ps1" and choose "Run with PowerShell"
2. Click "Yes" when Windows asks for administrator permission
3. The agent, scheduled task, and all files will be removed


IMPORTANT NOTES
---------------
- The setup code embedded in 1_install.ps1 expires after {ttl_hours} hour(s).
  If it has expired, download a fresh package from the HopMap dashboard.
- The installer is safe to run more than once (e.g. to repair or update).
- The installed files are located in {_INSTALL_DIR}\\.
"""


def build_installer(
    *,
    backend_url: str,
    setup_code: str,
    child_name: str,
) -> str:
    """Return a complete PowerShell installer script as a string.

    The setup code is interpolated at generation time.  It is short-lived
    (1 hour) and single-use — the agent calls POST /agent/activate on first
    run to exchange it for the real long-lived token, which is then stored
    locally.  This means the .ps1 file itself contains no permanently
    sensitive material.

    Args:
        backend_url:  Full URL of the HopMap server, e.g. https://hopmap.example.com
        setup_code:   One-time activation code issued by GET /agent/installer
        child_name:   Human-readable name used in log messages and task names
    """
    # Sanitise child_name for use in the Task Scheduler task name and folder.
    # Allow only alphanumeric + spaces; strip everything else.
    safe_name = "".join(c for c in child_name if c.isalnum() or c == " ").strip() or "child"

    file_downloads = "\n".join(
        f'    Invoke-WebRequest -Uri "$BackendUrl/agent/files/{f}" '
        f'-OutFile "$InstallDir\\{f}" -UseBasicParsing'
        for f in _AGENT_FILES
    )

    return f"""\
<#
.SYNOPSIS
    HopMap agent installer for {safe_name}.
.DESCRIPTION
    Installs Python, Tesseract OCR, the HopMap monitoring agent, and
    registers a Windows Task Scheduler task that starts the agent on login.
    Double-click to run - the script requests elevation automatically.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
trap {{ Write-Host ""; Write-Host "  [!] Unexpected error: $_" -ForegroundColor Red; Write-Host ""; $null = Read-Host "  Press Enter to close"; exit 1 }}

# Force TLS 1.2 - required by GitHub and most modern hosts (PS 5.1 defaults to TLS 1.0)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# -- Self-elevation: re-launch as Administrator if needed ---------------------
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    Start-Process PowerShell -Verb RunAs -WindowStyle Normal `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    [System.Environment]::Exit(0)
}}

$BackendUrl  = '{backend_url}'
$SetupCode   = '{setup_code}'
$ChildName   = '{safe_name}'
$InstallDir  = 'C:\\HopMap'
$TaskName    = "HopMap - $ChildName"

function Write-Step([string]$Msg) {{
    Write-Host "  [*] $Msg" -ForegroundColor Cyan
}}
function Write-Ok([string]$Msg) {{
    Write-Host "  [+] $Msg" -ForegroundColor Green
}}
function Write-Fail([string]$Msg) {{
    Write-Host "  [!] $Msg" -ForegroundColor Red
    Write-Host ""
    $null = Read-Host "  Press Enter to close"
    exit 1
}}

Write-Host ""
Write-Host "  HopMap Agent Installer" -ForegroundColor White
Write-Host "  -----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# -- 1. Python ----------------------------------------------------------------
Write-Step "Checking Python..."
$PythonCmd = $null
foreach ($candidate in @('python', 'python3', 'py')) {{
    try {{
        $ver = & $candidate --version 2>&1
        if ($ver -match 'Python 3\\.(?:1[0-9]|[2-9]\\d)') {{
            $PythonCmd = $candidate
            break
        }}
    }} catch {{ }}
}}

if (-not $PythonCmd) {{
    Write-Step "Python 3.10+ not found - installing via winget..."
    try {{
        winget install --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
        $PythonCmd = 'python'
    }} catch {{
        Write-Fail "winget install failed. Install Python 3.10+ from https://python.org and re-run this script."
    }}
}}
Write-Ok "Python: $(& $PythonCmd --version)"

# -- 2. Tesseract OCR ---------------------------------------------------------
Write-Step "Checking Tesseract OCR..."
$TesseractPath = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
$TesseractCmd = Get-Command tesseract -ErrorAction SilentlyContinue
if ($TesseractCmd) {{ $TesseractPath = $TesseractCmd.Source }}
if (-not (Test-Path $TesseractPath)) {{
    Write-Step "Tesseract not found - downloading..."
    $TmpInstaller = "$env:TEMP\\tesseract_setup.exe"
    Invoke-WebRequest -Uri '{_TESSERACT_URL}' -OutFile $TmpInstaller -UseBasicParsing

    Write-Step "Verifying download integrity..."
    $Hash = (Get-FileHash -Path $TmpInstaller -Algorithm SHA256).Hash
    if ($Hash -ne '{_TESSERACT_SHA256}') {{
        Remove-Item $TmpInstaller -Force
        Write-Fail "Tesseract download appears corrupt. Please try again."
    }}

    Write-Step "Installing Tesseract silently..."
    Start-Process -FilePath $TmpInstaller -ArgumentList '/S' -Wait
    Remove-Item $TmpInstaller -Force
}}
Write-Ok "Tesseract: $TesseractPath"

# -- 3. Create install directory ----------------------------------------------
Write-Step "Creating install directory $InstallDir..."
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Write-Ok "Directory ready: $InstallDir"

# -- 4. Download agent files --------------------------------------------------
Write-Step "Downloading agent files from $BackendUrl..."
{file_downloads}
Write-Ok "Agent files downloaded."

# -- 5. Write agent_config.json -----------------------------------------------
Write-Step "Writing agent configuration..."
$Config = @{{
    backend_url              = $BackendUrl
    scan_interval_seconds    = 5.0
    context_lines            = 10
    setup_code               = $SetupCode
    agent_token              = ''
}} | ConvertTo-Json
[System.IO.File]::WriteAllText("$InstallDir\\agent_config.json", $Config)
Write-Ok "agent_config.json written (agent will activate on first run)."

# -- 6. Install Python packages -----------------------------------------------
Write-Step "Installing Python packages..."
& $PythonCmd -m pip install -r "$InstallDir\\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) {{
    Write-Fail "pip install failed. Check your internet connection and try again."
}}
Write-Ok "Python packages installed."

# -- 7. Register Task Scheduler task ------------------------------------------
Write-Step "Registering Windows Task Scheduler task '$TaskName'..."
$PythonW = (& $PythonCmd -c "import sys, pathlib; print(pathlib.Path(sys.executable).parent / 'pythonw.exe')").Trim()

# Remove existing task with the same name (re-run safe)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action   = New-ScheduledTaskAction -Execute $PythonW -Argument 'agent.py' -WorkingDirectory $InstallDir
$Trigger  = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force | Out-Null

Write-Ok "Task '$TaskName' registered - agent will start automatically on login."

# Start the agent immediately without waiting for next login
Write-Step "Starting agent now..."
Start-ScheduledTask -TaskName $TaskName
Write-Ok "Agent started."

# -- Done ---------------------------------------------------------------------
Write-Host ""
Write-Host "  [OK] HopMap agent installed successfully for $ChildName." -ForegroundColor Green
Write-Host "  The agent is now running and will start automatically on every login." -ForegroundColor DarkGray
Write-Host ""
$null = Read-Host "  Press Enter to close"
"""
