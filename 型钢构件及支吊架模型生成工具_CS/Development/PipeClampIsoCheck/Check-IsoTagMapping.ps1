$ErrorActionPreference='Stop'
$installer=Join-Path $PSScriptRoot '../../Deployment/Install-PipeClampIsoTag.ps1'
$testBase=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'obj'))
$tempRoot=Join-Path $testBase ('SteelProbe-IsoTagCheck-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($tempRoot)
$fixture=Join-Path $tempRoot 'fixture.xml'
$backup=Join-Path $tempRoot 'backup'
$script:checks=0
function Check($pass,$name){$script:checks++;if(-not $pass){throw $name}}
function Reject([scriptblock]$action,$name){$failed=$false;try{& $action | Out-Null}catch{$failed=$true};Check $failed $name}
$xml=@'
<?xml version="1.0" encoding="utf-8"?>
<ECSchema schemaName="OpenPlant_3D_Supplemental_Isometrics_Isoextractor" xmlns="http://www.bentley.com/schemas/Bentley.ECXML.2.0">
 <ECClass typeName="PLANT_BASE_OBJECT"><ECCustomAttributes><BOM_LABELS xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><ECX_IE_SPEC>this.SPECIFICATION</ECX_IE_SPEC><OTH_ATTRIBUTES><BOM_ATTR_STRUCT><NAME>IE_TAG</NAME><ECX_VALUE>this.NAME</ECX_VALUE></BOM_ATTR_STRUCT><BOM_ATTR_STRUCT><NAME>IE_DESCRIPT</NAME><ECX_VALUE>this.DESCRIPTION</ECX_VALUE></BOM_ATTR_STRUCT></OTH_ATTRIBUTES></BOM_LABELS></ECCustomAttributes></ECClass>
 <ECClass typeName="SUPPORT_LOCATION"><ECCustomAttributes><IE_Component xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><IE_TYPE>CT_SUPPORT</IE_TYPE></IE_Component></ECCustomAttributes></ECClass>
 <ECClass typeName="PIPE"><ECCustomAttributes><Preserve xmlns="Other.Project.01.00">unchanged</Preserve></ECCustomAttributes></ECClass>
</ECSchema>
'@
[IO.File]::WriteAllText($fixture,$xml)
$before=[IO.File]::ReadAllBytes($fixture)
& $installer -SchemaPath $fixture | Out-Null
Check ([Convert]::ToBase64String($before) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($fixture))) 'dry run changed file'
Reject {& $installer -SchemaPath $fixture -Apply} 'apply without backup must fail'
& $installer -SchemaPath $fixture -BackupDirectory $backup -Apply | Out-Null
$doc=New-Object System.Xml.XmlDocument
$doc.Load($fixture)
$ns=New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
$ns.AddNamespace('ec',$doc.DocumentElement.NamespaceURI)
$ns.AddNamespace('iso','OpenPlant_IsoExtractor_Custom_Attributes.01.08')
$labelPath='ec:ECCustomAttributes/iso:BOM_LABELS/iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE'
$base=$doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="PLANT_BASE_OBJECT"]',$ns)
$support=$doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="SUPPORT_LOCATION"]',$ns)
$expected='IIf(IM.Match(this.DEVICE_TYPE_CODE,"SSPPC"),IM.GetValue("ALIAS",(this.NAME)),(this.NAME))'
Check ($base.SelectSingleNode($labelPath,$ns).InnerText -eq 'this.NAME') 'base tag modified'
Check ($support.SelectSingleNode($labelPath,$ns).InnerText -eq $expected) 'missing scoped ALIAS mapping with native fallback'
Check ($support.SelectNodes('ec:ECCustomAttributes/iso:IE_Component',$ns).Count -eq 1) 'existing support attributes lost'
Check ($support.SelectSingleNode('ec:ECCustomAttributes/iso:BOM_LABELS/iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_DESCRIPT"]/iso:ECX_VALUE',$ns).InnerText -eq 'this.DESCRIPTION') 'BOM description changed'
Check ($doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="PIPE"]',$ns).InnerText -eq 'unchanged') 'unrelated class changed'
$saved=(Get-ChildItem -LiteralPath $backup -Filter '*.bak')[0]
Check ([Convert]::ToBase64String($before) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($saved.FullName))) 'backup not byte exact'
$hash=(Get-FileHash -LiteralPath $fixture).Hash
& $installer -SchemaPath $fixture -BackupDirectory $backup -Apply | Out-Null
Check ((Get-FileHash -LiteralPath $fixture).Hash -eq $hash) 'reinstall changed file'
Check ((Get-ChildItem -LiteralPath $backup -Filter '*.bak').Count -eq 1) 'reinstall created unnecessary backup'
$support.SelectSingleNode($labelPath,$ns).InnerText='PROJECT_SPECIAL_TAG'
$doc.Save($fixture)
$hash=(Get-FileHash -LiteralPath $fixture).Hash
Reject {& $installer -SchemaPath $fixture -BackupDirectory $backup -Apply} 'must not overwrite existing project mapping'
Check ((Get-FileHash -LiteralPath $fixture).Hash -eq $hash) 'conflict changed file'
[IO.File]::WriteAllText($fixture,$xml.Replace('<ECClass typeName="SUPPORT_LOCATION"><ECCustomAttributes><IE_Component xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08"><IE_TYPE>CT_SUPPORT</IE_TYPE></IE_Component></ECCustomAttributes></ECClass>',''))
& $installer -SchemaPath $fixture -BackupDirectory $backup -Apply | Out-Null
$doc.Load($fixture)
Check ($doc.DocumentElement.SelectNodes('ec:ECClass[@typeName="SUPPORT_LOCATION"]',$ns).Count -eq 1) 'failed to add absent class'
[IO.File]::WriteAllText($fixture,$xml.Replace('<ECX_VALUE>this.NAME</ECX_VALUE>','<ECX_VALUE>this.NAME &amp; "-PROJECT"</ECX_VALUE>'))
& $installer -SchemaPath $fixture -BackupDirectory $backup -Apply | Out-Null
$doc.Load($fixture)
Check ($doc.DocumentElement.SelectSingleNode('ec:ECClass[@typeName="SUPPORT_LOCATION"]/'+$labelPath,$ns).InnerText.Contains('(this.NAME & "-PROJECT")')) 'original native fallback not preserved'
[IO.File]::WriteAllText($fixture,$xml.Replace('schemaName="OpenPlant_3D_Supplemental_Isometrics_Isoextractor"','schemaName="WrongSchema"'))
Reject {& $installer -SchemaPath $fixture -BackupDirectory $backup -Apply} 'wrong schema accepted'
$source=[IO.File]::ReadAllText((Join-Path $PSScriptRoot '../../Domain/NativePipeSupport/NativePipeSupportDefinition.cs'))
Check ($source.Contains('DeviceTypeCode = "SSPPC"')) 'marker differs from code'
# The generated directory contains only this check's fixtures and backups.
$resolvedTemp=[IO.Path]::GetFullPath($tempRoot)
if(-not $resolvedTemp.StartsWith($testBase+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {throw 'Cleanup target escaped test workspace'}
[IO.Directory]::Delete($resolvedTemp,$true)
Write-Output "PASS: $script:checks ISO tag mapping deployment checks (XML only, no ISO engine)."
