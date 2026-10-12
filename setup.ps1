param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$packageRoot = $PSScriptRoot
$venvRoot = Join-Path $packageRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts/python.exe'
$scratchRoot = Join-Path $packageRoot 'work'
New-Item -ItemType Directory -Force $scratchRoot | Out-Null
$savedTemp = $env:TEMP
$savedTmp = $env:TMP
try {
    $env:TEMP = $scratchRoot
    $env:TMP = $scratchRoot
    & $Python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
    if ($LASTEXITCODE -ne 0) { throw 'Choose a working Python 3.11+ executable with -Python.' }
    & $Python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    & $venvPython -m pip install -r (Join-Path $packageRoot 'requirements-lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $venvPython (Join-Path $packageRoot 'configure.py')
    if ($LASTEXITCODE -ne 0) { throw 'Configuration generation failed.' }
    Write-Host 'Ready. Read config-generated/CONNECTION_COMMANDS.txt to connect your clients.'
    Write-Host 'Codex/Claude configuration has not been changed.'
} finally {
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
}
