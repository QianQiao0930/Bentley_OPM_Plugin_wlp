$ErrorActionPreference='Stop'
# Install-NativeSupportEditing.ps1 -Features ValveActuator on isolated obj XML fixtures only.
$installer=Join-Path $PSScriptRoot '../../Deployment/Install-NativeSupportEditing.ps1'
$className='SSP_CEL_VALVE_ACTUATOR'
$testBase=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'obj'))
$temp=Join-Path $testBase ('ValveActuator-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($temp)
$backup=Join-Path $temp 'backup'
$script:checks=0
function Check($pass,$label){$script:checks++;if(-not $pass){throw $label}}
function Reject([scriptblock]$action,$label){$failed=$false;try{& $action | Out-Null}catch{$failed=$true};Check $failed $label}
$names=@('OpenPlant_3D','OpenPlant_3D_Supplemental_Modeling','OpenPlant_3D_Supplemental_Isometrics_Isoextractor')
$creation='<CREATION_ATTRIBUTE xmlns="OpenPlant_CustomAttributes.08.11"><ASSEMBLY_NAME>Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME><CLASS_NAME>GearBoxOperatorScript</CLASS_NAME><NAMESPACE>Bentley.Building.Mechanical.ComponentLibrary.ValveOperator</NAMESPACE><PLACEMENT_TOOL>TopworksPlacementTool</PLACEMENT_TOOL><HANDLER_TYPE>Topwork</HANDLER_TYPE><DIAGRAM_CELL_NAME>GEARBOX_OPERATOR</DIAGRAM_CELL_NAME><CELL_LIBRARY>TopWorksPreview.cel</CELL_LIBRARY></CREATION_ATTRIBUTE>'
$bodies=@(
 '<ECClass typeName="GEARBOX_OPERATOR"><BaseClass>MANUAL_VALVE_OPERATING_DEVICE</BaseClass></ECClass>',
 ('<ECClass typeName="GEARBOX_OPERATOR"><ECCustomAttributes>'+$creation+'</ECCustomAttributes></ECClass>'),
 '<ECClass typeName="PLANT_BASE_OBJECT" />'
)
$original=@{}
for($i=0;$i -lt $names.Count;$i++) {
 $path=Join-Path $temp ($names[$i]+'.01.08.ecschema.xml')
 $xml='<ECSchema schemaName="'+$names[$i]+'" xmlns="http://www.bentley.com/schemas/Bentley.ECXML.2.0">'+$bodies[$i]+'</ECSchema>'
 [IO.File]::WriteAllText($path,$xml)
 $original[$path]=[IO.File]::ReadAllBytes($path)
}
& $installer -SchemaDirectory $temp -Features ValveActuator | Out-Null
foreach($path in $original.Keys){Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) -eq [Convert]::ToBase64String($original[$path])) 'dry run changed schema'}
Reject {& $installer -SchemaDirectory $temp -Features ValveActuator -Apply} 'no backup accepted'
& $installer -SchemaDirectory $temp -Features ValveActuator -BackupDirectory $backup -Apply | Out-Null
$hashes=@{}
foreach($path in $original.Keys) {
 $doc=New-Object System.Xml.XmlDocument; $doc.Load($path)
 $nodes=$doc.SelectNodes('/*/*[@typeName="'+$className+'"]')
 $hashes[$path]=(Get-FileHash -LiteralPath $path).Hash
 if($path.Contains('Isoextractor')) {
  Check ($nodes.Count -eq 0) 'isoextractor must not change'
  Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) -eq [Convert]::ToBase64String($original[$path])) 'isoextractor rewritten'
  continue
 }
 Check ($nodes.Count -eq 1) 'one isolated actuator class'
 $old=New-Object System.Xml.XmlDocument; $old.LoadXml([Text.Encoding]::UTF8.GetString($original[$path]))
 Check ($doc.DocumentElement.FirstChild.OuterXml -eq $old.DocumentElement.FirstChild.OuterXml) 'stock GEARBOX_OPERATOR changed'
 $saved=Get-ChildItem -LiteralPath $backup -Filter ([IO.Path]::GetFileName($path)+'.*.bak')
 Check ($saved.Count -eq 1) 'missing backup'
 Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($saved[0].FullName)) -eq [Convert]::ToBase64String($original[$path])) 'backup not byte exact'
 if($path.Contains('Modeling')) {
  $text=$nodes[0].InnerXml
  Check ($text.Contains('<CLASS_NAME>CelValveActuatorComponent</CLASS_NAME>') -and $text.Contains('<ASSEMBLY_NAME>SteelSectionProbe</ASSEMBLY_NAME>')) 'wrong handler'
  Check ($text.Contains('<HANDLER_TYPE>Topwork</HANDLER_TYPE>') -and $text.Contains('<PLACEMENT_TOOL>TopworksPlacementTool</PLACEMENT_TOOL>')) 'native topwork contract lost'
 } else {
  Check ($nodes[0].FirstChild.InnerText -eq 'GEARBOX_OPERATOR') 'wrong inheritance'
  $props=@($nodes[0].SelectNodes('*[local-name()="ECProperty"]') | ForEach-Object { $_.GetAttribute('propertyName')+':'+$_.GetAttribute('typeName') })
  Check (($props -join ',') -eq 'SSP_CEL_VERSION:int,SSP_CEL_NAME:string,SSP_CEL_SOURCE:string,SSP_CEL_SHA256:string,SSP_CEL_DATA:binary,SSP_CEL_TOKEN:string') 'wrong CEL snapshot properties'
 }
}
& $installer -SchemaDirectory $temp -Features ValveActuator -BackupDirectory $backup -Apply | Out-Null
foreach($path in $hashes.Keys){Check ((Get-FileHash -LiteralPath $path).Hash -eq $hashes[$path]) 'reinstall changed schema'}
Check ((Get-ChildItem -LiteralPath $backup -Filter '*.bak').Count -eq 2) 'reinstall created new backups'
$conflict=Join-Path $temp ($names[1]+'.01.08.ecschema.xml')
[IO.File]::WriteAllText($conflict,[IO.File]::ReadAllText($conflict).Replace('<CLASS_NAME>CelValveActuatorComponent</CLASS_NAME>','<CLASS_NAME>ProjectCustomComponent</CLASS_NAME>'))
$conflictHash=(Get-FileHash -LiteralPath $conflict).Hash
Reject {& $installer -SchemaDirectory $temp -Features ValveActuator -BackupDirectory $backup -Apply} 'overwrote conflict'
Check ((Get-FileHash -LiteralPath $conflict).Hash -eq $conflictHash) 'conflict file changed'
$resolved=[IO.Path]::GetFullPath($temp)
if(-not $resolved.StartsWith($testBase+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Cleanup escaped workspace'}
[IO.Directory]::Delete($resolved,$true)
Write-Output "PASS: $script:checks ValveActuator schema deployment checks (XML only)."
