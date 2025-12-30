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

# Choose source for install
$sourceChoice = Read-Host "Install source? [1] GitHub download (default), [2] Local folder, [3] Offline zip"
if ([string]::IsNullOrWhiteSpace($sourceChoice)) {
    $sourceChoice = "1"
}
$appSourceDir = $root
$sourceLabel = $root
$tempDir = $null

if ($sourceChoice -eq "1") {
    $repoDefault = "twinsfan23/OBS-Scheduler"
    $repo = Read-Host "GitHub repo (owner/name) [default: $repoDefault]"
    if ([string]::IsNullOrWhiteSpace($repo)) {
        $repo = $repoDefault
    }
    $ref = Read-Host "Release tag (leave blank for main)"
    if ([string]::IsNullOrWhiteSpace($ref)) {
        $zipUrl = "https://github.com/$repo/archive/refs/heads/main.zip"
        $sourceLabel = "https://github.com/$repo (main)"
    } else {
        $zipUrl = "https://github.com/$repo/archive/refs/tags/$ref.zip"
        $sourceLabel = "https://github.com/$repo (tag $ref)"
    }
    $tempDir = Join-Path $env:TEMP ("obs-scheduler-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $zipPath = Join-Path $tempDir "repo.zip"
    Write-Host "Downloading $zipUrl"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Write-Host "Extracting archive..."
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
    $rootFolder = Get-ChildItem -Path $tempDir -Directory | Where-Object { $_.Name -ne ".venv" } | Select-Object -First 1
    if (-not $rootFolder) {
        Write-Error "Could not find extracted repo folder."
        exit 1
    }
    $appSourceDir = $rootFolder.FullName
} elseif ($sourceChoice -eq "3") {
    $zipPath = Read-Host "Path to offline zip file"
    if (-not (Test-Path $zipPath)) {
        Write-Error "Zip file not found: $zipPath"
        exit 1
    }
    $sourceLabel = $zipPath
    $tempDir = Join-Path $env:TEMP ("obs-scheduler-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    Write-Host "Extracting archive..."
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
    $rootFolder = Get-ChildItem -Path $tempDir -Directory | Select-Object -First 1
    if (-not $rootFolder) {
        Write-Error "Could not find extracted repo folder."
        exit 1
    }
    $appSourceDir = $rootFolder.FullName
} else {
    $sourceChoice = "2"
    $localRoot = Read-Host "Local repo folder (leave blank for current: $root)"
    if (-not [string]::IsNullOrWhiteSpace($localRoot)) {
        if (-not (Test-Path $localRoot)) {
            Write-Error "Local folder not found: $localRoot"
            exit 1
        }
        $appSourceDir = $localRoot
        $sourceLabel = $localRoot
    }
}

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
[System.IO.File]::WriteAllText((Join-Path $dataDir "repo-path.txt"), $sourceLabel, $utf8NoBom)

# TODO: When repo is on GitHub, download and extract into $appDir here.
Write-Host "Copying app files to $appDir"
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item -Path (Join-Path $appSourceDir "obs-scheduler-api") -Destination $appDir -Recurse -Force
Copy-Item -Path (Join-Path $appSourceDir "obs-video-scheduler") -Destination $appDir -Recurse -Force

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
$configPath = Join-Path $dataDir "config.json"
if (-not (Test-Path $configPath)) {
    $apiKey = [Guid]::NewGuid().ToString("N")
    $configJson = @"
{
  "api-key": "$apiKey",
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
"@
    Write-Host "Creating $configPath"
    Write-TextNoBom $configPath $configJson
    Write-Host "Writing API key to $(Join-Path $dataDir "api-key.txt")"
    Write-TextNoBom (Join-Path $dataDir "api-key.txt") $apiKey
} else {
    Ensure-JsonFile $configPath "{}"
}

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
$runBatSrc = Join-Path $appSourceDir "run-python.bat"
if (Test-Path $runBatSrc) {
    Copy-Item $runBatSrc -Destination (Join-Path $dataDir "run-python.bat") -Force
}

if ($tempDir -and (Test-Path $tempDir)) {
    Remove-Item -Recurse -Force $tempDir
}

Write-Host ""
Write-Host "Install complete."
Write-Host "1) Open OBS and enable obs-websocket (note port/password)."
Write-Host "2) Edit run-python.bat env vars if needed (OBS_HOST/PORT/PASSWORD/SCENE/LAYER)."
Write-Host "3) Your API key is saved in $(Join-Path $dataDir "api-key.txt")."
Write-Host "4) Launch with run-python.bat (at repo root or copied to $dataDir)"
