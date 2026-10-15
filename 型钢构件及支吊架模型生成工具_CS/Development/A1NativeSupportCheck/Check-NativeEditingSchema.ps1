param([ValidateSet('A1Trial','PipeClamp','Trunnion')][string]$Mode='A1Trial')
$ErrorActionPreference='Stop'
# 耳轴已改落自带类；Trunnion 模式只验 Isoextractor 三类 IE_TAG→ALIAS。
if($Mode -eq 'Trunnion') {
 & (Join-Path $PSScriptRoot '../PipeClampIsoCheck/Check-TrunnionStockIsoTag.ps1')
 return
}
$installer=Join-Path $PSScriptRoot $(switch($Mode){'A1Trial'{'../../Deployment/Install-A1NativeEditingTrial.ps1'} 'PipeClamp'{'../../Deployment/Install-PipeClampNativeEditing.ps1'}})
$className=switch($Mode){'A1Trial'{'SSP_A1_NATIVE_TEST'} 'PipeClamp'{'SSP_PIPE_CLAMP'}}
$componentName=if($Mode -eq 'A1Trial'){'A1NativeParametricComponent'}else{'NativePipeSupportComponent'}
$testBase=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'obj'))
$temp=Join-Path $testBase ('NativeEditing-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($temp)
$backup=Join-Path $temp 'backup'
$script:checks=0
function Check($pass,$label){$script:checks++;if(-not $pass){throw $label}}
function Reject([scriptblock]$action,$label){$failed=$false;try{& $action | Out-Null}catch{$failed=$true};Check $failed $label}
$names=@('OpenPlant_3D','OpenPlant_3D_Supplemental_Modeling','OpenPlant_3D_Supplemental_Isometrics_Isoextractor')
$bodies=@(
 '<ECClass typeName="SUPPORT_LOCATION"><BaseClass>SUPPORT</BaseClass></ECClass>',
 '<ECClass typeName="SUPPORT_LOCATION"><ECCustomAttributes><CREATION_ATTRIBUTE xmlns="OpenPlant_CustomAttributes.08.11"><ASSEMBLY_NAME>Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME><NAMESPACE>Bentley.Building.Mechanical.ComponentLibrary.Supports</NAMESPACE><CLASS_NAME>SupportLocation</CLASS_NAME><HANDLER_TYPE>Support</HANDLER_TYPE><PLACEMENT_TOOL>PipeSupportPlacementTool</PLACEMENT_TOOL></CREATION_ATTRIBUTE></ECCustomAttributes></ECClass>',
 '<ECClass typeName="PLANT_BASE_OBJECT"><ECCustomAttributes><BOM_LABELS xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><OTH_ATTRIBUTES><BOM_ATTR_STRUCT><NAME>IE_TAG</NAME><ECX_VALUE>this.NAME</ECX_VALUE></BOM_ATTR_STRUCT><BOM_ATTR_STRUCT><NAME>IE_DESCRIPT</NAME><ECX_VALUE>this.DESCRIPTION</ECX_VALUE></BOM_ATTR_STRUCT></OTH_ATTRIBUTES></BOM_LABELS></ECCustomAttributes></ECClass>'
)
$original=@{}
for($i=0;$i -lt $names.Count;$i++) {
 $path=Join-Path $temp ($names[$i]+'.01.08.ecschema.xml')
 $xml='<ECSchema schemaName="'+$names[$i]+'" xmlns="http://www.bentley.com/schemas/Bentley.ECXML.2.0">'+$bodies[$i]+'</ECSchema>'
 [IO.File]::WriteAllText($path,$xml)
 $original[$path]=[IO.File]::ReadAllBytes($path)
}
& $installer -SchemaDirectory $temp | Out-Null
foreach($path in $original.Keys){Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) -eq [Convert]::ToBase64String($original[$path])) 'dry run changed schema'}
Reject {& $installer -SchemaDirectory $temp -Apply} 'no backup accepted'
& $installer -SchemaDirectory $temp -BackupDirectory $backup -Apply | Out-Null
$hashes=@{}
foreach($path in $original.Keys) {
 $doc=New-Object System.Xml.XmlDocument; $doc.Load($path)
 $nodes=$doc.SelectNodes('/*/*[@typeName="'+$className+'"]')
 Check ($nodes.Count -eq 1) 'one isolated trial class'
 Check ($doc.DocumentElement.ChildNodes.Count -eq 2) 'existing class preserved'
 $old=New-Object System.Xml.XmlDocument; $old.LoadXml([Text.Encoding]::UTF8.GetString($original[$path]))
 Check ($doc.DocumentElement.FirstChild.OuterXml -eq $old.DocumentElement.FirstChild.OuterXml) 'stock class changed'
 $hashes[$path]=(Get-FileHash -LiteralPath $path).Hash
 $saved=Get-ChildItem -LiteralPath $backup -Filter ([IO.Path]::GetFileName($path)+'.*.bak')
 Check ($saved.Count -eq 1) 'missing backup'
 Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($saved[0].FullName)) -eq [Convert]::ToBase64String($original[$path])) 'backup not byte exact'
 if($path.Contains('Modeling')){
  Check ($nodes[0].InnerText.Contains($componentName) -and $nodes[0].InnerText.Contains('PipeSupportPlacementTool') -and $nodes[0].InnerText.Contains('Support')) 'wrong creation/handler'
 } elseif($path.Contains('Isoextractor')) {
  Check ($nodes[0].InnerText.Contains('this.ALIAS') -and $nodes[0].InnerText.Contains('this.DESCRIPTION')) 'wrong ISO mapping'
 } else {
  Check ($nodes[0].FirstChild.InnerText -eq 'SUPPORT_LOCATION') 'wrong inheritance'
  if($Mode -ne 'A1Trial'){Check ($nodes[0].SelectSingleNode('*[@propertyName="SSP_RECIPE"]') -ne $null) 'missing persistent recipe'}
 }
}
& $installer -SchemaDirectory $temp -BackupDirectory $backup -Apply | Out-Null
foreach($path in $hashes.Keys){Check ((Get-FileHash -LiteralPath $path).Hash -eq $hashes[$path]) 'reinstall changed schema'}
Check ((Get-ChildItem -LiteralPath $backup -Filter '*.bak').Count -eq 3) 'reinstall created new backups'
$conflict=Join-Path $temp ($names[1]+'.01.08.ecschema.xml')
[IO.File]::WriteAllText($conflict,[IO.File]::ReadAllText($conflict).Replace($componentName,'ProjectCustomComponent'))
$conflictHash=(Get-FileHash -LiteralPath $conflict).Hash
Reject {& $installer -SchemaDirectory $temp -BackupDirectory $backup -Apply} 'overwrote conflict'
Check ((Get-FileHash -LiteralPath $conflict).Hash -eq $conflictHash) 'conflict file changed'
foreach($path in $hashes.Keys){if($path -ne $conflict){Check ((Get-FileHash -LiteralPath $path).Hash -eq $hashes[$path]) 'other schemas changed on conflict'}}
$resolved=[IO.Path]::GetFullPath($temp)
if(-not $resolved.StartsWith($testBase+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Cleanup escaped workspace'}
[IO.Directory]::Delete($resolved,$true)
Write-Output "PASS: $script:checks $Mode schema deployment checks (XML only)."
