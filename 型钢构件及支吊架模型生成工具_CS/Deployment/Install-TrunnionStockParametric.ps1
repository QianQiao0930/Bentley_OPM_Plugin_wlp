# UTF-8 with BOM required for Windows PowerShell 5.1 Chinese text.
# 自带耳轴三类改为参数化组件（操作柄/随动），并保留原 ISO ClassMap。
# 关闭 OPM 后 -Apply；默认只读预览。
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SchemaDirectory,
    [string]$BackupDirectory,
    [switch]$Apply
)
$ErrorActionPreference='Stop'
$targets=@('SINGLE_PIPE_TRUNNION','DOUBLE_PIPE_TRUNNION','SIMPLE_ELBOW_SUPPORT')
$directory=(Resolve-Path -LiteralPath $SchemaDirectory).ProviderPath
$names=@('OpenPlant_3D','OpenPlant_3D_Supplemental_Modeling','OpenPlant_3D_Supplemental_Isometrics_Isoextractor')
$plans=@()
function Child($doc,$parent,$name,$value,$namespace) {
    $node=$doc.CreateElement($name,$namespace)
    $node.InnerText=$value
    [void]$parent.AppendChild($node)
}
foreach($schemaName in $names) {
    $path=Join-Path $directory ($schemaName+'.01.08.ecschema.xml')
    if(-not [IO.File]::Exists($path)){throw "缺少 Schema：$path"}
    $beforeHash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    $doc=New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace=$true
    $doc.Load($path)
    $root=$doc.DocumentElement
    if($root.LocalName -ne 'ECSchema' -or $root.GetAttribute('schemaName') -ne $schemaName){throw "Wrong schema: $path"}
    $ecns=$root.NamespaceURI
    $ns=New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
    $ns.AddNamespace('ec',$ecns)
    $ns.AddNamespace('op','OpenPlant_CustomAttributes.08.11')
    $ns.AddNamespace('iso','OpenPlant_IsoExtractor_Custom_Attributes.01.08')
    $fileChanged=$false
    $preview=@()
    foreach($typeName in $targets) {
        $cls=$root.SelectSingleNode('ec:ECClass[@typeName="'+$typeName+'"]',$ns)
        if($null -eq $cls){throw ("工作集缺少自带耳轴类 $typeName：$path")}
        if($schemaName -eq 'OpenPlant_3D') {
            $prop=$cls.SelectSingleNode('ec:ECProperty[@propertyName="SSP_RECIPE"]',$ns)
            if($null -eq $prop) {
                $p=$doc.CreateElement('ECProperty',$ecns)
                $p.SetAttribute('propertyName','SSP_RECIPE'); $p.SetAttribute('typeName','string')
                [void]$cls.AppendChild($p)
                $fileChanged=$true
                $preview += "将写入：$typeName +SSP_RECIPE"
            } else {
                if($prop.GetAttribute('typeName') -ne 'string'){throw "$typeName.SSP_RECIPE 类型不是 string，禁止覆盖。"}
                $preview += "已安装：$typeName.SSP_RECIPE"
            }
        } elseif($schemaName -eq 'OpenPlant_3D_Supplemental_Modeling') {
            $attrs=$cls.SelectSingleNode('ec:ECCustomAttributes',$ns)
            if($null -eq $attrs){$attrs=$doc.CreateElement('ECCustomAttributes',$ecns);[void]$cls.AppendChild($attrs)}
            $creation=$attrs.SelectSingleNode('op:CREATION_ATTRIBUTE',$ns)
            $stock=$root.SelectSingleNode('ec:ECClass[@typeName="SUPPORT_LOCATION"]/ec:ECCustomAttributes/op:CREATION_ATTRIBUTE',$ns)
            if($null -eq $stock){throw 'SUPPORT_LOCATION 缺 CREATION_ATTRIBUTE，无法克隆。'}
            if($null -eq $creation) {
                $creation=$stock.CloneNode($true)
                [void]$attrs.AppendChild($creation)
                $fileChanged=$true
            }
            $assembly=$creation.SelectSingleNode('op:ASSEMBLY_NAME',$ns)
            $namespaceNode=$creation.SelectSingleNode('op:NAMESPACE',$ns)
            $classNode=$creation.SelectSingleNode('op:CLASS_NAME',$ns)
            $handler=$creation.SelectSingleNode('op:HANDLER_TYPE',$ns)
            $tool=$creation.SelectSingleNode('op:PLACEMENT_TOOL',$ns)
            if($null -eq $assembly -or $null -eq $namespaceNode -or $null -eq $classNode -or $null -eq $handler){throw "$typeName CREATION_ATTRIBUTE 字段不完整。"}
            $already=($assembly.InnerText -eq 'SteelSectionProbe' -and $namespaceNode.InnerText -eq 'SteelSectionProbe' -and $classNode.InnerText -eq 'NativePipeSupportComponent')
            if($already) {
                if($handler.InnerText -ne 'Support'){throw "$typeName 已指向本插件但 HANDLER_TYPE 不是 Support。"}
                $preview += "已安装：$typeName → NativePipeSupportComponent"
            } else {
                # 仅允许从自带 Bentley 组件切到本插件；其它项目定制拒绝覆盖。
                if($assembly.InnerText -eq 'SteelSectionProbe' -and $classNode.InnerText -ne 'NativePipeSupportComponent') {
                    throw "$typeName 已有其它 SteelSectionProbe 组件 $($classNode.InnerText)，禁止覆盖。"
                }
                $assembly.InnerText='SteelSectionProbe'
                $namespaceNode.InnerText='SteelSectionProbe'
                $classNode.InnerText='NativePipeSupportComponent'
                $handler.InnerText='Support'
                if($null -ne $tool){$tool.InnerText='PipeSupportPlacementTool'}
                $fileChanged=$true
                $preview += "将写入：$typeName CREATION_ATTRIBUTE → NativePipeSupportComponent"
            }
        } else {
            # Isoextractor：仅确保 IE_TAG=ALIAS，不改 ClassMap/符号。
            $attrs=$cls.SelectSingleNode('ec:ECCustomAttributes',$ns)
            if($null -eq $attrs){$attrs=$doc.CreateElement('ECCustomAttributes',$ecns);[void]$cls.AppendChild($attrs)}
            $labels=$attrs.SelectSingleNode('iso:BOM_LABELS',$ns)
            if($null -eq $labels) {
                $base=$root.SelectSingleNode('ec:ECClass[@typeName="PLANT_BASE_OBJECT"]/ec:ECCustomAttributes/iso:BOM_LABELS',$ns)
                if($null -eq $base){throw 'PLANT_BASE_OBJECT 缺 BOM_LABELS。'}
                $labels=$base.CloneNode($true)
                $tag=$labels.SelectSingleNode('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
                if($null -eq $tag){throw '默认 IE_TAG 缺失。'}
                $tag.InnerText='this.ALIAS'
                [void]$attrs.AppendChild($labels)
                $fileChanged=$true
                $preview += "将写入：$typeName IE_TAG=this.ALIAS"
            } else {
                $tag=$labels.SelectSingleNode('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
                if($null -ne $tag -and $tag.InnerText -eq 'this.ALIAS') {
                    $preview += "已安装：$typeName IE_TAG=this.ALIAS"
                } else {
                    throw "$typeName 已有项目自定义 BOM 标签，禁止覆盖；请人工将 IE_TAG 改为 this.ALIAS。"
                }
            }
        }
    }
    $preview | ForEach-Object { Write-Output $_ }
    if($fileChanged){$plans+=@{Path=$path;Document=$doc;BeforeSHA256=$beforeHash}}
}
if(-not $Apply){ if($plans.Count -eq 0){Write-Output '无需修改：自带耳轴参数化与引注已安装。'}; return }
if($plans.Count -eq 0){Write-Output '无需修改：自带耳轴参数化与引注已安装。'; return }
if([string]::IsNullOrWhiteSpace($BackupDirectory)){throw '-Apply必须指定-BackupDirectory。'}
# 正式工作集安装时必须关 OPM；Development/*/obj 隔离夹具检查可跳过。
$isOfflineFixture = $directory -match '[\\/]Development[\\/].+[\\/]obj([\\/]|$)'
if(-not $isOfflineFixture -and (Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(OpenPlantModeler|ustation)$' -and -not $_.HasExited })){throw '请先关闭 OPM 再安装 Schema。'}
$backupRoot=[IO.Path]::GetFullPath($BackupDirectory)
[void][IO.Directory]::CreateDirectory($backupRoot)
$receipt=@()
try {
    foreach($plan in $plans) {
        $backup=Join-Path $backupRoot ([IO.Path]::GetFileName($plan.Path)+'.'+[Guid]::NewGuid().ToString('N')+'.bak')
        [IO.File]::Copy($plan.Path,$backup,$false)
        if((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $plan.BeforeSHA256){throw '备份校验失败。'}
        $plan.Backup=$backup
        $plan.Temporary=$plan.Path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
        $settings=New-Object System.Xml.XmlWriterSettings
        $settings.Encoding=New-Object System.Text.UTF8Encoding($false)
        $settings.Indent=$false
        $settings.NewLineHandling=[System.Xml.NewLineHandling]::None
        $writer=[System.Xml.XmlWriter]::Create($plan.Temporary,$settings)
        try{$plan.Document.Save($writer)}finally{$writer.Dispose()}
        $check=New-Object System.Xml.XmlDocument
        $check.Load($plan.Temporary)
    }
    foreach($plan in $plans) {
        if((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.BeforeSHA256){throw '准备期间 Schema 被修改，停止写入。'}
        [IO.File]::Replace($plan.Temporary,$plan.Path,[System.Management.Automation.Language.NullString]::Value)
        $plan.Applied=$true
        $plan.AfterSHA256=(Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash
        $receipt+=@{Schema=$plan.Path;Backup=$plan.Backup;BeforeSHA256=$plan.BeforeSHA256;AfterSHA256=$plan.AfterSHA256}
    }
} catch {
    $failure=$_
    $rollbackErrors=@()
    foreach($plan in $plans) {
        if($plan.Applied) {
            try {
                if((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.AfterSHA256){throw '写入后文件又被改动，拒绝回滚覆盖。'}
                [IO.File]::Copy($plan.Backup,$plan.Path,$true)
            } catch { $rollbackErrors+=$_.Exception.Message }
        }
    }
    if($rollbackErrors.Count){throw ($failure.Exception.Message+' 回滚未完成：'+($rollbackErrors -join '; '))}
    throw $failure
} finally {
    foreach($plan in $plans){if($plan.Temporary -and [IO.File]::Exists($plan.Temporary)){[IO.File]::Delete($plan.Temporary)}}
}
$receiptPath=Join-Path $backupRoot ('TrunnionStockParametric-'+[Guid]::NewGuid().ToString('N')+'.json')
$receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Output ('已安装自带耳轴参数化组件。收据：'+$receiptPath)
