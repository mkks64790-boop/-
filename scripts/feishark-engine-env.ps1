# Session env for workspace-bundled engines (source before launcher/self_check).
$projectRoot = Split-Path -Parent $PSScriptRoot
$external = Join-Path $projectRoot "external"

$env:FEISHARK_RVC_DIR = Join-Path $external "rvc-webui"
$env:FEISHARK_RVC_BACKUP_DIR = Join-Path $external "rvc-webui-backup"
$env:FEISHARK_AUDIO_PIPELINE = Join-Path $external "audio-pipeline"
$env:FEISHARK_RVC_PORT = "7866"
$env:FEISHARK_RVC_BACKUP_PORT = "7865"
$env:FEISHARK_RVC_API = "http://127.0.0.1:7866"
$env:FEISHARK_RVC_BACKUP_API = "http://127.0.0.1:7865"

# Bundled venv is minimal; use the working Conda env when present.
$condaRvc = "D:\Miniconda3\envs\rvc\python.exe"
if (Test-Path -LiteralPath $condaRvc) {
    $env:FEISHARK_RVC_PYTHON = $condaRvc
    $env:FEISHARK_RVC_BACKUP_PYTHON = $condaRvc
} else {
    $bundled = Join-Path $env:FEISHARK_RVC_DIR "venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $bundled) {
        $env:FEISHARK_RVC_PYTHON = $bundled
        $env:FEISHARK_RVC_BACKUP_PYTHON = $bundled
    }
}

if (-not $env:FEISHARK_RVC_GPUS) { $env:FEISHARK_RVC_GPUS = "0" }

Write-Host "FEISHARK_RVC_DIR=$($env:FEISHARK_RVC_DIR)"
Write-Host "FEISHARK_RVC_BACKUP_DIR=$($env:FEISHARK_RVC_BACKUP_DIR)"
Write-Host "FEISHARK_AUDIO_PIPELINE=$($env:FEISHARK_AUDIO_PIPELINE)"
Write-Host "FEISHARK_RVC_PYTHON=$($env:FEISHARK_RVC_PYTHON)"