$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $project 'bin\Release\net48_full\SteelSectionProbe.dll'
$target = Join-Path $project 'bin\Release\net48\SteelSectionProbe.dll'
if (-not (Test-Path -LiteralPath $source)) { throw "Missing compiled DLL: $source" }
$librarySource = Join-Path $project 'bin\Release\net48_full\地面冲洗水盘管.cel'
$libraryTarget = Join-Path $project 'bin\Release\net48\地面冲洗水盘管.cel'
if (-not (Test-Path -LiteralPath $librarySource)) { throw "Missing CEL library: $librarySource" }
try {
    Copy-Item -LiteralPath $source -Destination $target -Force -ErrorAction Stop
    Copy-Item -LiteralPath $librarySource -Destination $libraryTarget -Force -ErrorAction Stop
} catch {
    throw 'Close all OpenPlant Modeler windows before updating the loaded DLL. Original error: ' + $_.Exception.Message
}
$expected = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'Copied DLL hash mismatch' }
$libraryExpected = (Get-FileHash -LiteralPath $librarySource -Algorithm SHA256).Hash
$libraryActual = (Get-FileHash -LiteralPath $libraryTarget -Algorithm SHA256).Hash
if ($libraryActual -ne $libraryExpected) { throw 'Copied CEL library hash mismatch' }
Write-Output "SteelSectionProbe updated: $actual"
Write-Output "CEL library updated: $libraryActual"
