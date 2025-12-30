$ErrorActionPreference = "Stop"

Write-Host "=== OBS Scheduler (Python) installer ==="
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Working directory: $root"
$defaultDir = "C:\scheduler"
$installDir = Read-Host "Install directory (default: $defaultDir)"
if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = $defaultDir
}
$dataDir = $installDir
$appDir = Join-Path $dataDir "app"
$schedulesDir = Join-Path $dataDir "schedules"
Write-Host "Data directory will be: $dataDir"

# Check Python
Write-Host "Checking Python..."
try {
    python --version
} catch {
    Write-Error "Python not found. Install Python 3.10+ and ensure 'python' is on PATH."
    exit 1
}

# Ensure data structure
Write-Host "Ensuring data directory at $dataDir"
New-Item -ItemType Directory -Force -Path $schedulesDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $dataDir "repo-path.txt"), $root, $utf8NoBom)

# TODO: When repo is on GitHub, download and extract into $appDir here.
# For now, copy app files from the local repo next to this script.
Write-Host "Copying app files to $appDir"
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item -Path (Join-Path $root "obs-scheduler-api") -Destination $appDir -Recurse -Force
Copy-Item -Path (Join-Path $root "obs-video-scheduler") -Destination $appDir -Recurse -Force

function Write-TextNoBom($path, $content) {
    [System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
}

function Ensure-JsonFile($path, $default) {
    if (-not (Test-Path $path)) {
        Write-Host "Creating $path"
        Write-TextNoBom $path $default
    }
}

function Normalize-TextFile($path) {
    if (Test-Path $path) {
        $content = Get-Content -Path $path -Raw
        Write-TextNoBom $path $content
    }
}

Ensure-JsonFile (Join-Path $dataDir "filelist.txt") "[]"
Ensure-JsonFile (Join-Path $dataDir "alist.txt") "[]"
Ensure-JsonFile (Join-Path $dataDir "schedule.json") "[]"
if (-not (Test-Path (Join-Path $dataDir "timestamp"))) {
    Write-TextNoBom (Join-Path $dataDir "timestamp") ([string]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()))
}
Ensure-JsonFile (Join-Path $dataDir "config.json") @'
{
  "server-video-dir": "C:/videos/",
  "obs-video-dir": "C:/videos/",
  "scene-name": "Scene 1",
  "idle-scene-enabled": false,
  "idle-scene-name": "Slides",
  "source-layer": "1",
  "sources-to-mute": [],
  "video-top-margin": "0",
  "video-left-margin": "0",
  "video-width": "100",
  "video-height": "100",
  "obs-host": "localhost",
  "obs-port": "4455",
  "obs-password": "",
  "ffprobe-path": "",
  "disclaimer-file-name": "",
  "disclaimer-transition-time": "0"
}
'@

Normalize-TextFile (Join-Path $dataDir "filelist.txt")
Normalize-TextFile (Join-Path $dataDir "alist.txt")
Normalize-TextFile (Join-Path $dataDir "schedule.json")
Normalize-TextFile (Join-Path $dataDir "timestamp")
Normalize-TextFile (Join-Path $dataDir "config.json")

# Set up venv and deps
$apiDir = Join-Path $appDir "obs-scheduler-api"
$venvDir = Join-Path $dataDir ".venv"
Write-Host "Creating virtual environment in $venvDir"
python -m venv $venvDir

Write-Host "Installing Python dependencies..."
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment python not found."
    exit 1
}
Push-Location $apiDir
& $venvPython -m pip install -r requirements.txt
Pop-Location

# Copy run script to data dir for convenience
$runBatSrc = Join-Path $root "run-python.bat"
if (Test-Path $runBatSrc) {
    Copy-Item $runBatSrc -Destination (Join-Path $dataDir "run-python.bat") -Force
}

Write-Host ""
Write-Host "Install complete."
Write-Host "1) Open OBS and enable obs-websocket (note port/password)."
Write-Host "2) Edit run-python.bat env vars if needed (OBS_HOST/PORT/PASSWORD/SCENE/LAYER)."
Write-Host "3) Launch with run-python.bat (at repo root or copied to $dataDir)"
