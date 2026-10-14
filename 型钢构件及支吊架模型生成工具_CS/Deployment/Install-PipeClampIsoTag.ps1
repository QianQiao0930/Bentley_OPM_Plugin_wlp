# Run with OPM closed, then restart OPM and regenerate the isometric.
# Without -Apply this is read-only and prints the exact proposed class mapping.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SchemaPath,
    [string]$BackupDirectory,
    [switch]$Apply
)
$ErrorActionPreference='Stop'
$resolved=(Resolve-Path -LiteralPath $SchemaPath).ProviderPath
$doc=New-Object System.Xml.XmlDocument
$doc.PreserveWhitespace=$true
$doc.Load($resolved)
$ecns=$doc.DocumentElement.NamespaceURI
$ns=New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
$ns.AddNamespace('ec',$ecns)
$ns.AddNamespace('iso','OpenPlant_IsoExtractor_Custom_Attributes.01.08')
$root=$doc.DocumentElement
if($root.LocalName -ne 'ECSchema' -or $root.GetAttribute('schemaName') -ne 'OpenPlant_3D_Supplemental_Isometrics_Isoextractor') {
    throw '请选择工作集的OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml。'
}
$base=$root.SelectSingleNode('ec:ECClass[@typeName="PLANT_BASE_OBJECT"]/ec:ECCustomAttributes/iso:BOM_LABELS',$ns)
if($null -eq $base){throw '未找到PLANT_BASE_OBJECT默认BOM标签，停止写入。'}
$copy=$base.CloneNode($true)
$tags=$copy.SelectNodes('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
if($tags.Count -ne 1 -or [string]::IsNullOrWhiteSpace($tags[0].InnerText)){throw '默认IE_TAG映射不唯一或为空，停止写入。'}
$fallback=$tags[0].InnerText
$expression='IIf(IM.Match(this.DEVICE_TYPE_CODE,"SSPPC"),IM.GetValue("ALIAS",('+ $fallback +')),('+ $fallback +'))'
$tags[0].InnerText=$expression
$target=$root.SelectSingleNode('ec:ECClass[@typeName="SUPPORT_LOCATION"]',$ns)
if($null -ne $target) {
    $existing=$target.SelectSingleNode('ec:ECCustomAttributes/iso:BOM_LABELS',$ns)
    if($null -ne $existing) {
        $oldTag=$existing.SelectSingleNode('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
        if($null -ne $oldTag -and $oldTag.InnerText -eq $expression) {
            Write-Output '无需修改：该工作集已安装管夹AssemblyTag引注映射。'
            return
        }
        throw 'SUPPORT_LOCATION已有项目自定义BOM标签，禁止覆盖；请人工合并IE_TAG条件表达式。'
    }
} else {
    $target=$doc.CreateElement('ECClass',$ecns)
    $target.SetAttribute('typeName','SUPPORT_LOCATION')
    $target.SetAttribute('isDomainClass','False')
    [void]$root.AppendChild($doc.CreateWhitespace("`r`n    "))
    [void]$root.AppendChild($target)
    [void]$root.AppendChild($doc.CreateWhitespace("`r`n"))
}
$attrs=$target.SelectSingleNode('ec:ECCustomAttributes',$ns)
if($null -eq $attrs){$attrs=$doc.CreateElement('ECCustomAttributes',$ecns);[void]$target.AppendChild($attrs)}
[void]$attrs.AppendChild($copy)
if(-not $Apply){Write-Output $target.OuterXml;return}
if([string]::IsNullOrWhiteSpace($BackupDirectory)){throw '-Apply必须指定-BackupDirectory，不能无备份修改工作集。'}
$backupRoot=[IO.Path]::GetFullPath($BackupDirectory)
[void][IO.Directory]::CreateDirectory($backupRoot)
$beforeHash=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
$backupName=[IO.Path]::GetFileName($resolved)+'.'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.'+[Guid]::NewGuid().ToString('N')+'.bak'
$backupPath=Join-Path $backupRoot $backupName
[IO.File]::Copy($resolved,$backupPath,$false)
if((Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash -ne $beforeHash){throw '备份校验失败，停止写入。'}
$temporary=$resolved+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
try {
    $settings=New-Object System.Xml.XmlWriterSettings
    $settings.Encoding=New-Object System.Text.UTF8Encoding($false)
    $settings.Indent=$false
    $settings.NewLineHandling=[System.Xml.NewLineHandling]::None
    $writer=[System.Xml.XmlWriter]::Create($temporary,$settings)
    try{$doc.Save($writer)}finally{$writer.Dispose()}
    $check=New-Object System.Xml.XmlDocument
    $check.Load($temporary)
    if((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash -ne $beforeHash){throw '工作集文件在准备期间被其他程序修改，停止替换。'}
    [IO.File]::Replace($temporary,$resolved,[System.Management.Automation.Language.NullString]::Value)
} finally {
    if([IO.File]::Exists($temporary)){[IO.File]::Delete($temporary)}
}
$receipt=@{Schema=$resolved;Backup=$backupPath;BeforeSHA256=$beforeHash;AfterSHA256=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash;IE_TAG=$expression}
$receipt | ConvertTo-Json | Set-Content -LiteralPath ($backupPath+'.json') -Encoding UTF8
Write-Output ($receipt | ConvertTo-Json)
