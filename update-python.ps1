$ErrorActionPreference = "Stop"

Write-Host "=== OBS Scheduler updater ==="
$defaultDir = "C:\scheduler"
$installDir = Read-Host "Install directory (default: $defaultDir)"
if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = $defaultDir
}
$dataDir = $installDir
$appDir = Join-Path $dataDir "app"
Write-Host "Updating install at: $dataDir"

if (-not (Test-Path $appDir)) {
    Write-Error "App folder not found at $appDir. Run install-python.ps1 first."
    exit 1
}

$configPath = Join-Path $dataDir "config.json"
$apiKeyPath = Join-Path $dataDir "api-key.txt"
if (-not (Test-Path $configPath)) {
    Write-Error "Missing config.json at $configPath. Run install-python.ps1 first."
    exit 1
}
try {
    $configJson = Get-Content -Path $configPath -Raw -ErrorAction Stop | ConvertFrom-Json
} catch {
    $configJson = $null
}
if (-not $configJson) {
    $configJson = New-Object psobject
}
if (-not $configJson.PSObject.Properties.Name.Contains("api-key") -or -not $configJson."api-key") {
    $newKey = [Guid]::NewGuid().ToString("N")
    $configJson | Add-Member -NotePropertyName "api-key" -NotePropertyValue $newKey -Force
    $configJson | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding utf8
    $newKey | Set-Content -Path $apiKeyPath -Encoding ascii
    Write-Host "Generated API key and saved to $apiKeyPath"
}

$sourceChoice = Read-Host "Update source? [1] GitHub download (default), [2] Local folder, [3] Offline zip"
if ([string]::IsNullOrWhiteSpace($sourceChoice)) {
    $sourceChoice = "1"
}
$appSourceDir = $null
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
    } else {
        $zipUrl = "https://github.com/$repo/archive/refs/tags/$ref.zip"
    }
    $tempDir = Join-Path $env:TEMP ("obs-scheduler-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $zipPath = Join-Path $tempDir "repo.zip"
    Write-Host "Downloading $zipUrl"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Write-Host "Extracting archive..."
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
    $rootFolder = Get-ChildItem -Path $tempDir -Directory | Select-Object -First 1
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
    $localRoot = Read-Host "Local repo folder"
    if ([string]::IsNullOrWhiteSpace($localRoot) -or -not (Test-Path $localRoot)) {
        Write-Error "Local folder not found: $localRoot"
        exit 1
    }
    $appSourceDir = $localRoot
}

Write-Host "Updating app files in $appDir"
if (Test-Path (Join-Path $appDir "obs-scheduler-api")) {
    Remove-Item -Recurse -Force (Join-Path $appDir "obs-scheduler-api")
}
if (Test-Path (Join-Path $appDir "obs-video-scheduler")) {
    Remove-Item -Recurse -Force (Join-Path $appDir "obs-video-scheduler")
}
Copy-Item -Path (Join-Path $appSourceDir "obs-scheduler-api") -Destination $appDir -Recurse -Force
Copy-Item -Path (Join-Path $appSourceDir "obs-video-scheduler") -Destination $appDir -Recurse -Force

$runBatSrc = Join-Path $appSourceDir "run-python.bat"
if (Test-Path $runBatSrc) {
    Copy-Item $runBatSrc -Destination (Join-Path $dataDir "run-python.bat") -Force
}

$venvPython = Join-Path $dataDir ".venv\\Scripts\\python.exe"
if (Test-Path $venvPython) {
    $apiDir = Join-Path $appDir "obs-scheduler-api"
    Write-Host "Updating Python dependencies..."
    Push-Location $apiDir
    & $venvPython -m pip install -r requirements.txt
    Pop-Location
} else {
    Write-Host "Virtual environment not found; skipping dependency update."
}

if ($tempDir -and (Test-Path $tempDir)) {
    Remove-Item -Recurse -Force $tempDir
}

Write-Host ""
Write-Host "Update complete."
