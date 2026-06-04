$ErrorActionPreference = "Stop"

function Test-HttpUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 8
        return $true
    } catch {
        return $false
    }
}

function Wait-HttpUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSeconds = 60,
        [int]$IntervalSeconds = 2
    )

    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-HttpUrl -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds $IntervalSeconds
        $elapsed += $IntervalSeconds
        Write-Host ("Waiting... ({0}s / {1}s)" -f $elapsed, $TimeoutSeconds)
    }

    return $false
}

Write-Host "=============================================="
Write-Host "FeiShark Studio Launcher"
Write-Host "=============================================="
Write-Host ""

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$logDir = Join-Path $projectRoot "logs"
$null = New-Item -ItemType Directory -Path $logDir -Force

$apiPort = 8000
$rvcPort = if ($env:FEISHARK_RVC_PORT) { [int]$env:FEISHARK_RVC_PORT } else { 7866 }
$rvcUrl = "http://127.0.0.1:$rvcPort"

$rvcDir = $env:FEISHARK_RVC_DIR
if (-not $rvcDir) {
    $projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    foreach ($candidate in @(
        (Join-Path $projectRoot "external\rvc-webui"),
        (Join-Path $projectRoot "external\rvc"),
        "D:\RVC\RVCv2",
        "D:\RVC\RVC",
        "C:\Users\ASUS\WorkBuddy\20260427153731\RVC-WebUI"
    )) {
        if (Test-Path (Join-Path $candidate "infer-web.py")) {
            $rvcDir = $candidate
            break
        }
    }
}

$rvcPython = $env:FEISHARK_RVC_PYTHON
if (-not $rvcPython) {
    foreach ($candidate in @(
        $(if ($rvcDir) { Join-Path $rvcDir "runtime\python.exe" }),
        $(if ($rvcDir) { Join-Path $rvcDir "venv\Scripts\python.exe" }),
        "D:\Miniconda3\envs\rvc\python.exe"
    )) {
        if ($candidate -and (Test-Path $candidate)) {
            $rvcPython = $candidate
            break
        }
    }
}
if (-not $rvcPython) {
    $rvcPython = "python"
}

$env:FEISHARK_RVC_API = $rvcUrl
$env:FEISHARK_RVC_PORT = "$rvcPort"
if ($rvcDir) {
    $env:FEISHARK_RVC_DIR = $rvcDir
}
if ($rvcPython) {
    $env:FEISHARK_RVC_PYTHON = $rvcPython
}

Write-Host "[1/4] Environment check..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found on PATH."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Python OK"
Write-Host ("Project:    {0}" -f $projectRoot)
Write-Host ("Backend:    {0}" -f $backendDir)
if ($rvcDir) {
    Write-Host ("RVC_DIR:    {0}" -f $rvcDir)
} else {
    Write-Host "RVC_DIR:    <not found>"
}
Write-Host ("RVC_PYTHON: {0}" -f $rvcPython)
Write-Host ""

Write-Host "[2/4] RVC engine..."
if (Test-HttpUrl -Url "$rvcUrl/gradio_api/info") {
    Write-Host ("RVC already running at {0}" -f $rvcUrl)
} elseif ($rvcDir -and (Test-Path (Join-Path $rvcDir "infer-web.py"))) {
    Write-Host ("Starting RVC at {0}" -f $rvcUrl)
    Start-Process `
        -WindowStyle Hidden `
        -FilePath $rvcPython `
        -WorkingDirectory $rvcDir `
        -ArgumentList @("infer-web.py", "--pycmd", $rvcPython, "--port", "$rvcPort", "--noautoopen") `
        -RedirectStandardOutput (Join-Path $logDir "rvc.stdout.log") `
        -RedirectStandardError (Join-Path $logDir "rvc.stderr.log")

    if (Wait-HttpUrl -Url "$rvcUrl/gradio_api/info" -TimeoutSeconds 60 -IntervalSeconds 2) {
        Write-Host "RVC ready"
    } else {
        Write-Host "RVC start timeout"
    }
} else {
    Write-Host "RVC WebUI not found. Skip RVC startup."
}
Write-Host ""

# --- Backup RVC for 秋风RVC (as enabled in FeiShark Studio) ---
$backupRvcPort = if ($env:FEISHARK_RVC_BACKUP_PORT) { [int]$env:FEISHARK_RVC_BACKUP_PORT } else { 7865 }
$backupRvcUrl = "http://127.0.0.1:$backupRvcPort"
$backupRvcDir = $env:FEISHARK_RVC_BACKUP_DIR
if (-not $backupRvcDir) {
    $backupRvcDir = Join-Path $projectRoot "external\rvc-webui-backup"
    if (-not (Test-Path (Join-Path $backupRvcDir "infer-web.py"))) {
        $backupRvcDir = Join-Path $projectRoot "external\rvc-qiufeng"
        if (-not (Test-Path (Join-Path $backupRvcDir "infer-web.py"))) {
            $backupRvcDir = $null
        }
    }
}
$backupRvcPython = $env:FEISHARK_RVC_BACKUP_PYTHON
if (-not $backupRvcPython -and $backupRvcDir) {
    foreach ($candidate in @(
        $(if ($backupRvcDir) { Join-Path $backupRvcDir "runtime\python.exe" }),
        $(if ($backupRvcDir) { Join-Path $backupRvcDir "venv\Scripts\python.exe" }),
        "D:\Miniconda3\envs\rvc\python.exe"
    )) {
        if ($candidate -and (Test-Path $candidate)) {
            $backupRvcPython = $candidate
            break
        }
    }
}
if ($backupRvcDir -and (Test-Path (Join-Path $backupRvcDir "infer-web.py"))) {
    if (Test-HttpUrl -Url "$backupRvcUrl/gradio_api/info") {
        Write-Host ("Backup RVC (秋风RVC) already running at {0}" -f $backupRvcUrl)
    } else {
        Write-Host ("Starting backup RVC (for 秋风RVC backup in studio) at {0}" -f $backupRvcUrl)
        Start-Process `
            -WindowStyle Hidden `
            -FilePath $(if ($backupRvcPython) { $backupRvcPython } else { "python" }) `
            -WorkingDirectory $backupRvcDir `
            -ArgumentList @("infer-web.py", "--pycmd", $(if ($backupRvcPython) { $backupRvcPython } else { "python" }), "--port", "$backupRvcPort", "--noautoopen") `
            -RedirectStandardOutput (Join-Path $logDir "rvc-backup.stdout.log") `
            -RedirectStandardError (Join-Path $logDir "rvc-backup.stderr.log")
        if (Wait-HttpUrl -Url "$backupRvcUrl/gradio_api/info" -TimeoutSeconds 60 -IntervalSeconds 2) {
            Write-Host "Backup RVC ready"
        } else {
            Write-Host "Backup RVC start timeout (秋风RVC may need manual start or model load in webui)"
        }
    }
    $env:FEISHARK_RVC_BACKUP_DIR = $backupRvcDir
    $env:FEISHARK_RVC_BACKUP_PORT = "$backupRvcPort"
    $env:FEISHARK_RVC_BACKUP_API = $backupRvcUrl
} else {
    Write-Host "Backup RVC dir not found in workspace/external or env. 秋风RVC backup in studio will use main or manual instance."
}
Write-Host ""

Write-Host "[3/4] FastAPI backend..."
if (Test-HttpUrl -Url "http://127.0.0.1:$apiPort/api/health") {
    Write-Host ("Backend already running at http://127.0.0.1:{0}" -f $apiPort)
} else {
    Write-Host ("Starting backend at http://127.0.0.1:{0}" -f $apiPort)
    Start-Process `
        -WindowStyle Hidden `
        -FilePath "python" `
        -WorkingDirectory $projectRoot `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$apiPort", "--log-level", "warning") `
        -RedirectStandardOutput (Join-Path $logDir "backend.stdout.log") `
        -RedirectStandardError (Join-Path $logDir "backend.stderr.log")

    Start-Sleep -Seconds 3
    if (Test-HttpUrl -Url "http://127.0.0.1:$apiPort/api/health") {
        Write-Host "Backend ready"
    } else {
        Write-Host "Backend start failed"
    }
}
Write-Host ""

Write-Host "[4/4] Open browser..."
Start-Process "http://127.0.0.1:$apiPort/"
Write-Host ("Frontend: http://127.0.0.1:{0}/" -f $apiPort)
Write-Host ("API:      http://127.0.0.1:{0}/api/health" -f $apiPort)
Write-Host ("Docs:     http://127.0.0.1:{0}/docs" -f $apiPort)
Write-Host ("RVC:      {0}" -f $rvcUrl)
Write-Host ""

if (-not $env:FEISHARK_NO_PAUSE) {
    Read-Host "Press Enter to exit"
}
