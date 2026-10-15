# Offline XML checks for stock trunnion parametric + IE_TAG installer.
$ErrorActionPreference='Stop'
$installer=Join-Path $PSScriptRoot '../../Deployment/Install-TrunnionStockParametric.ps1'
$testBase=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'obj'))
$tempRoot=Join-Path $testBase ('SteelProbe-TrunnionStock-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($tempRoot)
$backup=Join-Path $tempRoot 'backup'
$script:checks=0
function Check($pass,$name){$script:checks++;if(-not $pass){throw $name}}
function Reject([scriptblock]$action,$name){$failed=$false;try{& $action | Out-Null}catch{$failed=$true};Check $failed $name}
function LoadNs($doc) {
 $n=New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
 [void]$n.AddNamespace('ec',$doc.DocumentElement.NamespaceURI)
 [void]$n.AddNamespace('op','OpenPlant_CustomAttributes.08.11')
 [void]$n.AddNamespace('iso','OpenPlant_IsoExtractor_Custom_Attributes.01.08')
 ,$n
}
$names=@('OpenPlant_3D','OpenPlant_3D_Supplemental_Modeling','OpenPlant_3D_Supplemental_Isometrics_Isoextractor')
$bodies=@(
 @'
<ECClass typeName="SUPPORT_LOCATION"><BaseClass>SUPPORT</BaseClass></ECClass>
<ECClass typeName="SINGLE_PIPE_TRUNNION"><BaseClass>SUPPORT_LOCATION</BaseClass></ECClass>
<ECClass typeName="DOUBLE_PIPE_TRUNNION"><BaseClass>SUPPORT_LOCATION</BaseClass></ECClass>
<ECClass typeName="SIMPLE_ELBOW_SUPPORT"><BaseClass>SUPPORT_LOCATION</BaseClass></ECClass>
'@,
 @'
<ECClass typeName="SUPPORT_LOCATION"><ECCustomAttributes><CREATION_ATTRIBUTE xmlns="OpenPlant_CustomAttributes.08.11"><ASSEMBLY_NAME>Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME><NAMESPACE>Bentley.Building.Mechanical.ComponentLibrary.Supports</NAMESPACE><CLASS_NAME>SupportLocation</CLASS_NAME><HANDLER_TYPE>Support</HANDLER_TYPE><PLACEMENT_TOOL>PipeSupportPlacementTool</PLACEMENT_TOOL></CREATION_ATTRIBUTE></ECCustomAttributes></ECClass>
<ECClass typeName="SINGLE_PIPE_TRUNNION"><ECCustomAttributes><CREATION_ATTRIBUTE xmlns="OpenPlant_CustomAttributes.08.11"><ASSEMBLY_NAME>Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME><NAMESPACE>Bentley.Building.Mechanical.ComponentLibrary.Supports</NAMESPACE><CLASS_NAME>SinglePipeTrunnion</CLASS_NAME><HANDLER_TYPE>Support</HANDLER_TYPE><PLACEMENT_TOOL>PipeSupportPlacementTool</PLACEMENT_TOOL></CREATION_ATTRIBUTE></ECCustomAttributes></ECClass>
<ECClass typeName="DOUBLE_PIPE_TRUNNION"><ECCustomAttributes><CREATION_ATTRIBUTE xmlns="OpenPlant_CustomAttributes.08.11"><ASSEMBLY_NAME>Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME><NAMESPACE>Bentley.Building.Mechanical.ComponentLibrary.Supports</NAMESPACE><CLASS_NAME>DoublePipeTrunnion</CLASS_NAME><HANDLER_TYPE>Support</HANDLER_TYPE><PLACEMENT_TOOL>PipeSupportPlacementTool</PLACEMENT_TOOL></CREATION_ATTRIBUTE></ECCustomAttributes></ECClass>
<ECClass typeName="SIMPLE_ELBOW_SUPPORT"><ECCustomAttributes><CREATION_ATTRIBUTE xmlns="OpenPlant_CustomAttributes.08.11"><ASSEMBLY_NAME>Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME><NAMESPACE>Bentley.Building.Mechanical.ComponentLibrary.Supports</NAMESPACE><CLASS_NAME>SimpleElbowSupport</CLASS_NAME><HANDLER_TYPE>Support</HANDLER_TYPE><PLACEMENT_TOOL>PipeSupportPlacementTool</PLACEMENT_TOOL></CREATION_ATTRIBUTE></ECCustomAttributes></ECClass>
'@,
 @'
<ECClass typeName="PLANT_BASE_OBJECT"><ECCustomAttributes><BOM_LABELS xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><OTH_ATTRIBUTES><BOM_ATTR_STRUCT><NAME>IE_TAG</NAME><ECX_VALUE>this.NAME</ECX_VALUE></BOM_ATTR_STRUCT><BOM_ATTR_STRUCT><NAME>IE_DESCRIPT</NAME><ECX_VALUE>this.DESCRIPTION</ECX_VALUE></BOM_ATTR_STRUCT></OTH_ATTRIBUTES></BOM_LABELS></ECCustomAttributes></ECClass>
<ECClass typeName="SINGLE_PIPE_TRUNNION"><ECCustomAttributes><IE_Component xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><IE_TYPE>CT_SUPPORT</IE_TYPE></IE_Component><ClassMap xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><ClassName>SUPP_TRUNNION</ClassName></ClassMap></ECCustomAttributes></ECClass>
<ECClass typeName="DOUBLE_PIPE_TRUNNION"><ECCustomAttributes><IE_Component xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><IE_TYPE>CT_SUPPORT</IE_TYPE></IE_Component><ClassMap xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><ClassName>SUPP_TRUNNION</ClassName></ClassMap></ECCustomAttributes></ECClass>
<ECClass typeName="SIMPLE_ELBOW_SUPPORT"><ECCustomAttributes><IE_Component xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><IE_TYPE>CT_SUPPORT</IE_TYPE></IE_Component><ClassMap xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><ClassName>SUPP_ELBOW</ClassName></ClassMap></ECCustomAttributes></ECClass>
'@
)
$original=@{}
for($i=0;$i -lt $names.Count;$i++) {
 $path=Join-Path $tempRoot ($names[$i]+'.01.08.ecschema.xml')
 $xml='<ECSchema schemaName="'+$names[$i]+'" xmlns="http://www.bentley.com/schemas/Bentley.ECXML.2.0">'+$bodies[$i]+'</ECSchema>'
 [IO.File]::WriteAllText($path,$xml)
 $original[$path]=[IO.File]::ReadAllBytes($path)
}
& $installer -SchemaDirectory $tempRoot | Out-Null
foreach($path in $original.Keys){Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) -eq [Convert]::ToBase64String($original[$path])) 'dry run changed schema'}
Reject {& $installer -SchemaDirectory $tempRoot -Apply} 'no backup accepted'
& $installer -SchemaDirectory $tempRoot -BackupDirectory $backup -Apply | Out-Null
foreach($typeName in @('SINGLE_PIPE_TRUNNION','DOUBLE_PIPE_TRUNNION','SIMPLE_ELBOW_SUPPORT')) {
 $doc=New-Object System.Xml.XmlDocument; $doc.Load((Join-Path $tempRoot 'OpenPlant_3D.01.08.ecschema.xml')); $ns=LoadNs $doc
 Check ($doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="'+$typeName+'"]/ec:ECProperty[@propertyName="SSP_RECIPE"]',$ns) -ne $null) "missing recipe $typeName"
 $doc=New-Object System.Xml.XmlDocument; $doc.Load((Join-Path $tempRoot 'OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml')); $ns=LoadNs $doc
 $creation=$doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="'+$typeName+'"]/ec:ECCustomAttributes/op:CREATION_ATTRIBUTE',$ns)
 Check ($creation.SelectSingleNode('op:CLASS_NAME',$ns).InnerText -eq 'NativePipeSupportComponent') "wrong component $typeName"
 Check ($creation.SelectSingleNode('op:HANDLER_TYPE',$ns).InnerText -eq 'Support') "wrong handler $typeName"
 $doc=New-Object System.Xml.XmlDocument; $doc.Load((Join-Path $tempRoot 'OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml')); $ns=LoadNs $doc
 $cls=$doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="'+$typeName+'"]',$ns)
 Check ($cls.SelectSingleNode('ec:ECCustomAttributes/iso:BOM_LABELS/iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns).InnerText -eq 'this.ALIAS') "missing ALIAS $typeName"
 Check ($cls.SelectNodes('ec:ECCustomAttributes/iso:ClassMap',$ns).Count -eq 1) "lost ClassMap $typeName"
}
$baseFile=Join-Path $tempRoot 'OpenPlant_3D.01.08.ecschema.xml'
$hash=(Get-FileHash -LiteralPath $baseFile).Hash
& $installer -SchemaDirectory $tempRoot -BackupDirectory $backup -Apply | Out-Null
Check ((Get-FileHash -LiteralPath $baseFile).Hash -eq $hash) 'reinstall changed base schema'
$conflict=Join-Path $tempRoot 'OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml'
$text=[IO.File]::ReadAllText($conflict).Replace('NativePipeSupportComponent','ProjectCustomComponent')
[IO.File]::WriteAllText($conflict,$text)
$conflictHash=(Get-FileHash -LiteralPath $conflict).Hash
Reject {& $installer -SchemaDirectory $tempRoot -BackupDirectory $backup -Apply} 'overwrote conflict'
Check ((Get-FileHash -LiteralPath $conflict).Hash -eq $conflictHash) 'conflict file changed'
$resolvedTemp=[IO.Path]::GetFullPath($tempRoot)
if(-not $resolvedTemp.StartsWith($testBase+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Cleanup escaped workspace'}
[IO.Directory]::Delete($resolvedTemp,$true)
Write-Output "PASS: $script:checks stock trunnion parametric schema checks (XML only)."
