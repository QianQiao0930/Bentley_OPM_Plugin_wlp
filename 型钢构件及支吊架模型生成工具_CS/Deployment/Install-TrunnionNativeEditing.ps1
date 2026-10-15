# UTF-8 with BOM required for Windows PowerShell 5.1 Chinese text.
# 耳轴/弯头耳轴落自带类：参数化组件（滑动/旋转操作柄）+ ISO 引注 ALIAS，保留 SUPP_TRUNNION/SUPP_ELBOW。
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SchemaDirectory,
    [string]$BackupDirectory,
    [switch]$Apply
)
$ErrorActionPreference='Stop'
$args=@{SchemaDirectory=$SchemaDirectory}
if($PSBoundParameters.ContainsKey('BackupDirectory')){$args.BackupDirectory=$BackupDirectory}
if($Apply){$args.Apply=$true}
& (Join-Path $PSScriptRoot 'Install-TrunnionStockParametric.ps1') @args
