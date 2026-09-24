$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$source = Join-Path $project 'bin\Release\net48_full\SteelSectionProbe.dll'
$target = Join-Path $project 'bin\Release\net48\SteelSectionProbe.dll'
if (-not (Test-Path -LiteralPath $source)) { throw "Missing compiled DLL: $source" }
try {
    Copy-Item -LiteralPath $source -Destination $target -Force -ErrorAction Stop
} catch {
    throw 'Close all OpenPlant Modeler windows before updating the loaded DLL. Original error: ' + $_.Exception.Message
}
$expected = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'Copied DLL hash mismatch' }
Write-Output "SteelSectionProbe updated: $actual"
