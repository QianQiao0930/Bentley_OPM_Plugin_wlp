<#
.SYNOPSIS
    把编译好的 PipeAlign.dll 复制到一个「AddIn 目录」，并打印在 OPM 里的加载步骤。

.DESCRIPTION
    本脚本刻意只做两件确定性的事：复制 + SHA256 校验 + 打印加载说明。
    它**不会**去改 OPM 的配置、注册表或 MS_ADDINPATH 环境变量 —— 那些是机器级设置，
    由使用者自己决定作用范围（当前会话 / 用户 / 系统）。

.PARAMETER TargetDirectory
    目标目录。默认 `%LOCALAPPDATA%\PipeAlign\addin`。

.PARAMETER BentleyRoot
    Bentley 根目录，仅用于在提示里显示；默认与工程一致。

.EXAMPLE
    pwsh -File Deployment\install_to_addinpath.ps1
    pwsh -File Deployment\install_to_addinpath.ps1 -TargetDirectory 'D:\OPM_Addins\PipeAlign'
#>
[CmdletBinding()]
param(
    [string]$TargetDirectory,
    [string]$BentleyRoot = 'D:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler'
)

$ErrorActionPreference = 'Stop'

$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $project 'bin\Release\net48\PipeAlign.dll'

if (-not (Test-Path -LiteralPath $source)) {
    throw "找不到编译产物：$source`n请先在工程目录执行：dotnet build PipeAlign.csproj -c Release"
}

if ([string]::IsNullOrWhiteSpace($TargetDirectory)) {
    $TargetDirectory = Join-Path $env:LOCALAPPDATA 'PipeAlign\addin'
}
if (-not (Test-Path -LiteralPath $TargetDirectory)) {
    New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
}
$target = Join-Path $TargetDirectory 'PipeAlign.dll'

try {
    Copy-Item -LiteralPath $source -Destination $target -Force -ErrorAction Stop
}
catch {
    throw "复制失败。若 OPM 正在运行且已加载过本插件，请先关闭 OPM 再试。原始错误：$($_.Exception.Message)"
}

$expected = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw '复制后的 DLL 哈希不一致，请重试。' }

Write-Output "PipeAlign.dll 已就位：$target"
Write-Output "SHA256 = $actual"
Write-Output ''
Write-Output '在 OpenPlant Modeler 里这样加载：'
Write-Output '  1) 让 OPM 能找到这个目录，二者选一：'
Write-Output "     · 把   $TargetDirectory   加入 MS_ADDINPATH（用分号分隔多个目录）"
Write-Output '     · 或把 PipeAlign.dll 直接放进已在 MS_ADDINPATH 里的目录'
Write-Output "  2) 启动 OPM（Bentley 根目录：$BentleyRoot）"
Write-Output '  3) 键入  MDL LOAD PipeAlign'
Write-Output '  4) 键入  PIPEALIGN           打开窗口'
Write-Output '            PIPEALIGN DEBUG     只读打印选中管道的调试数据（建议第一次先跑这个）'
Write-Output ''
Write-Output '提示：升级 DLL 前必须先关掉 OPM —— 已加载的程序集无法被覆盖。'
