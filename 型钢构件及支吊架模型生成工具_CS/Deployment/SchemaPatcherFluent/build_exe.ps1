# Build SchemaPatcherFluent.exe (PySide6 + FluentQt) with PyInstaller inside .venv; output: dist\SchemaPatcherFluent.exe
[CmdletBinding()]
param(
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python (FluentQt needs Python 3.11-3.13)" }
    & $Python -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& $venvPython -m pip install --disable-pip-version-check --quiet FluentQt pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
$engine = Join-Path (Split-Path $root -Parent) 'SchemaPatcher'
Push-Location $root
try {
    & $venvPython -m PyInstaller --noconfirm --clean --onefile --windowed --name SchemaPatcherFluent `
        --paths (Join-Path $root 'src') --paths $engine `
        --collect-all fluentqt `
        --hidden-import app.main --hidden-import schema_patcher.engine `
        --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build') --specpath (Join-Path $root 'build') `
        (Join-Path $root 'SchemaPatcherFluent.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
} finally { Pop-Location }
$exe = Join-Path $root 'dist\SchemaPatcherFluent.exe'
Write-Output ("Built: $exe")
Write-Output ("Size: {0:N1} MB" -f ((Get-Item -LiteralPath $exe).Length / 1MB))
Write-Output ("SHA256: " + (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash)
