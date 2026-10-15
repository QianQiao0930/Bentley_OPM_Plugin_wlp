# UTF-8 with BOM required for Windows PowerShell 5.1 Chinese text.
# 薄入口：只装正式管夹隔离类 SSP_PIPE_CLAMP。实现见 Install-NativeSupportEditing.ps1。
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SchemaDirectory,
    [string]$BackupDirectory,
    [switch]$Apply
)
$forward=@{SchemaDirectory=$SchemaDirectory;Features='PipeClamp'}
if($PSBoundParameters.ContainsKey('BackupDirectory')){$forward.BackupDirectory=$BackupDirectory}
if($Apply){$forward.Apply=$true}
& (Join-Path $PSScriptRoot 'Install-NativeSupportEditing.ps1') @forward
