# UTF-8 with BOM required for Windows PowerShell 5.1 Chinese text.
# Patches stock SINGLE/DOUBLE/ELBOW trunnion classes so IE_TAG reads ALIAS.
# Keeps existing ClassMap / IE_VALUE_MAP (SUPP_TRUNNION / SUPP_ELBOW). Close OPM before -Apply.
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
$targets=@('SINGLE_PIPE_TRUNNION','DOUBLE_PIPE_TRUNNION','SIMPLE_ELBOW_SUPPORT')
$expression='this.ALIAS'
$changed=$false
$preview=@()
foreach($typeName in $targets) {
    $target=$root.SelectSingleNode('ec:ECClass[@typeName="'+$typeName+'"]',$ns)
    if($null -eq $target){throw ("工作集缺少自带耳轴类 $typeName，无法安装引注映射。")}
    $attrs=$target.SelectSingleNode('ec:ECCustomAttributes',$ns)
    if($null -eq $attrs){
        $attrs=$doc.CreateElement('ECCustomAttributes',$ecns)
        [void]$target.AppendChild($attrs)
    }
    $existing=$attrs.SelectSingleNode('iso:BOM_LABELS',$ns)
    if($null -ne $existing) {
        $oldTag=$existing.SelectSingleNode('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
        if($null -ne $oldTag -and $oldTag.InnerText -eq $expression) {
            $preview += ("已安装：$typeName IE_TAG=$expression")
            continue
        }
        throw ("$typeName 已有项目自定义BOM标签，禁止覆盖；请人工将IE_TAG改为this.ALIAS并保留原ClassMap/符号映射。")
    }
    $copy=$base.CloneNode($true)
    $tags=$copy.SelectNodes('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
    if($tags.Count -ne 1 -or [string]::IsNullOrWhiteSpace($tags[0].InnerText)){throw '默认IE_TAG映射不唯一或为空，停止写入。'}
    $tags[0].InnerText=$expression
    [void]$attrs.AppendChild($copy)
    $changed=$true
    $preview += ("将写入：$typeName IE_TAG=$expression（保留原IE_Component/ClassMap）")
}
if(-not $Apply){ $preview | ForEach-Object { Write-Output $_ }; if(-not $changed){Write-Output '无需修改：三类自带耳轴引注映射已安装。'}; return }
if(-not $changed){ Write-Output '无需修改：三类自带耳轴引注映射已安装。'; return }
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
$receipt=@{Schema=$resolved;Backup=$backupPath;BeforeSHA256=$beforeHash;AfterSHA256=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash;IE_TAG=$expression;Classes=$targets}
$receipt | ConvertTo-Json | Set-Content -LiteralPath ($backupPath+'.json') -Encoding UTF8
Write-Output ($receipt | ConvertTo-Json)
