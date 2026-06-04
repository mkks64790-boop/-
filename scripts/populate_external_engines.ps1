# Populate workspace external/ engines from discovered local installs.
# Governance-safe: copy/link only; does not train/infer/download models.

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$external = Join-Path $projectRoot "external"
$primaryDst = Join-Path $external "rvc-webui"
$backupDst = Join-Path $external "rvc-webui-backup"
$audioDst = Join-Path $external "audio-pipeline"

$primarySrc = "D:\RVC\RVCv2"
$audioSrc = "C:\Users\ASUS\AudioPipeline"

$robocopyExcludeDirs = @("/XD", "logs", ".git", "__pycache__", "wheel_cache", "node_modules")

function Invoke-Robo([string]$Src, [string]$Dst, [string[]]$ExtraArgs) {
    if (-not (Test-Path -LiteralPath $Src)) {
        throw "Source missing: $Src"
    }
    $args = @($Src, $Dst, "/E", "/COPY:DAT", "/R:1", "/W:2", "/NFL", "/NDL", "/NP") + $robocopyExcludeDirs + $ExtraArgs
    Write-Host ">> robocopy $($args -join ' ')"
    & robocopy @args | Out-Host
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit $LASTEXITCODE for $Src -> $Dst" }
}

Write-Host "=== Populate external engines ==="
Invoke-Robo -Src $primarySrc -Dst $primaryDst -ExtraArgs @()

# Training filelist needs logs/mute (excluded from main tree copy).
$muteSrc = Join-Path $primarySrc "logs\mute"
$muteDst = Join-Path $primaryDst "logs\mute"
if (Test-Path -LiteralPath $muteSrc) {
    Invoke-Robo -Src $muteSrc -Dst $muteDst -ExtraArgs @()
} else {
    Write-Warning "RVC mute assets missing at $muteSrc — training may fail until logs/mute is present."
}

Invoke-Robo -Src $audioSrc -Dst $audioDst -ExtraArgs @()

# Backup: full tree except logs; weights junction to primary to avoid duplicate ~30GB.
if (Test-Path -LiteralPath $backupDst) {
    Remove-Item -LiteralPath $backupDst -Recurse -Force
}
Invoke-Robo -Src $primaryDst -Dst $backupDst -ExtraArgs @("/XD", "assets\weights")

$backupWeights = Join-Path $backupDst "assets\weights"
$primaryWeights = Join-Path $primaryDst "assets\weights"
New-Item -ItemType Directory -Path (Join-Path $backupDst "assets") -Force | Out-Null
if (Test-Path -LiteralPath $backupWeights) { Remove-Item -LiteralPath $backupWeights -Force -Recurse -ErrorAction SilentlyContinue }
cmd /c mklink /J "$backupWeights" "$primaryWeights" | Out-Host

Write-Host "DONE populate_external_engines"