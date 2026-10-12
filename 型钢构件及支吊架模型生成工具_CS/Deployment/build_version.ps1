param(
    [ValidateSet('Licensed', 'Unlicensed')]
    [string]$Edition = 'Licensed'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$projectFile = Join-Path $projectRoot 'SteelSupportModeler.csproj'
$licensing = if ($Edition -eq 'Licensed') { 'true' } else { 'false' }
$outputPath = if ($Edition -eq 'Licensed') { 'bin\Release\net48_full\' } else { 'bin\Release\Unlicensed\' }

# 两种产物分别保存；本脚本只编译，不覆盖 OPM 正在加载的 DLL。
& dotnet build $projectFile -c Release "-p:EnableLicensing=$licensing" "-p:OutDir=$outputPath" --nologo
if ($LASTEXITCODE -ne 0) { throw "Build failed: $Edition" }

$assemblyPath = Join-Path $projectRoot ($outputPath + 'SteelSectionProbe.dll')
$hash = (Get-FileHash -LiteralPath $assemblyPath -Algorithm SHA256).Hash
Write-Output "$Edition DLL: $assemblyPath"
Write-Output "SHA256: $hash"
