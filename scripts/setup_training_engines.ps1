# Prepare workspace-local engine folders for FeiShark Studio.
#
# Safe governance-mode behavior:
# - creates directory skeletons only
# - does not clone, download, train, infer, or start UVR/RVC
# - lets the user drop complete engines into external/
#
# Usage from project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_training_engines.ps1

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$externalDir = Join-Path $projectRoot "external"
$primaryRvcDir = Join-Path $externalDir "rvc-webui"
$backupRvcDir = Join-Path $externalDir "rvc-webui-backup"
$audioPipelineDir = Join-Path $externalDir "audio-pipeline"

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-EngineStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RequiredFile
    )
    $requiredPath = Join-Path $Root $RequiredFile
    $ready = Test-Path -LiteralPath $requiredPath
    $status = if ($ready) { "READY" } else { "DROP_IN_REQUIRED" }
    Write-Host ("{0}: {1}" -f $Label, $status)
    Write-Host ("  root:     {0}" -f $Root)
    Write-Host ("  required: {0}" -f $RequiredFile)
}

Write-Host "=== FeiShark Training Engine Workspace Setup ==="
Write-Host ("Project:  {0}" -f $projectRoot)
Write-Host ("External: {0}" -f $externalDir)
Write-Host ""

Ensure-Directory $externalDir
Ensure-Directory $primaryRvcDir
Ensure-Directory (Join-Path $primaryRvcDir "assets")
Ensure-Directory (Join-Path $primaryRvcDir "assets\weights")
Ensure-Directory (Join-Path $primaryRvcDir "assets\indices")
Ensure-Directory (Join-Path $primaryRvcDir "logs")

Ensure-Directory $backupRvcDir
Ensure-Directory (Join-Path $backupRvcDir "assets")
Ensure-Directory (Join-Path $backupRvcDir "assets\weights")
Ensure-Directory (Join-Path $backupRvcDir "assets\indices")
Ensure-Directory (Join-Path $backupRvcDir "logs")

Ensure-Directory $audioPipelineDir
Ensure-Directory (Join-Path $audioPipelineDir "models")

Write-EngineStatus -Label "Primary RVC WebUI (port 7866, training + inference)" -Root $primaryRvcDir -RequiredFile "infer-web.py"
Write-EngineStatus -Label "Backup RVC WebUI (port 7865, inference fallback)" -Root $backupRvcDir -RequiredFile "infer-web.py"
Write-EngineStatus -Label "AudioPipeline / UVR" -Root $audioPipelineDir -RequiredFile "run_uvr5_split.py"
Write-Host ""

$env:FEISHARK_RVC_DIR = $primaryRvcDir
$env:FEISHARK_RVC_BACKUP_DIR = $backupRvcDir
$env:FEISHARK_AUDIO_PIPELINE = $audioPipelineDir
$env:FEISHARK_RVC_PORT = "7866"
$env:FEISHARK_RVC_BACKUP_PORT = "7865"
$env:FEISHARK_RVC_API = "http://127.0.0.1:7866"
$env:FEISHARK_RVC_BACKUP_API = "http://127.0.0.1:7865"

Write-Host "Session environment prepared:"
Write-Host ("  FEISHARK_RVC_DIR={0}" -f $env:FEISHARK_RVC_DIR)
Write-Host ("  FEISHARK_RVC_BACKUP_DIR={0}" -f $env:FEISHARK_RVC_BACKUP_DIR)
Write-Host ("  FEISHARK_AUDIO_PIPELINE={0}" -f $env:FEISHARK_AUDIO_PIPELINE)
Write-Host ""
Write-Host "Next manual step: copy complete engine deployments into the three external folders."
Write-Host "No engine was downloaded, started, trained, or executed by this script."
