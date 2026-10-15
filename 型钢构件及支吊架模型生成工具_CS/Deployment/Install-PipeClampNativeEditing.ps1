[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SchemaDirectory,[string]$BackupDirectory,[switch]$Apply)
& (Join-Path $PSScriptRoot 'Install-NativeSupportSchema.ps1') @PSBoundParameters -Mode PipeClamp
