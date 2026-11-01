# Build SchemaPatcher.exe with PyInstaller inside an isolated venv (.build-venv); output: dist\SchemaPatcher.exe
[CmdletBinding()]
param(
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python (use -Python <path to python.exe with tkinter>)" }
$venv = Join-Path $root '.build-venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& $venvPython -m pip install --disable-pip-version-check --quiet --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'pip install pyinstaller failed' }
Push-Location $root
try {
    & $venvPython -m PyInstaller --noconfirm --clean --onefile --windowed --name SchemaPatcher `
        --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build') --specpath (Join-Path $root 'build') `
        (Join-Path $root 'SchemaPatcher.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
} finally { Pop-Location }
$exe = Join-Path $root 'dist\SchemaPatcher.exe'
Write-Output ("Built: $exe")
Write-Output ("SHA256: " + (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash)
