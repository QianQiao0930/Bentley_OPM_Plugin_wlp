# UTF-8 with BOM required for Windows PowerShell 5.1 Chinese text.
# 兼容入口：-Mode PipeClamp 转发到 Install-NativeSupportEditing.ps1 -Features PipeClamp。
# （旧 -Mode Trunnion 隔离类方案已随自带类方案一并作废，不再支持。）
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SchemaDirectory,
    [ValidateSet('PipeClamp')][string]$Mode='PipeClamp',
    [string]$BackupDirectory,
    [switch]$Apply
)
$forward=@{SchemaDirectory=$SchemaDirectory;Features='PipeClamp'}
if($PSBoundParameters.ContainsKey('BackupDirectory')){$forward.BackupDirectory=$BackupDirectory}
if($Apply){$forward.Apply=$true}
& (Join-Path $PSScriptRoot 'Install-NativeSupportEditing.ps1') @forward
