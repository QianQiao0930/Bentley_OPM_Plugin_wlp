# Adds one isolated class; never changes the stock SUPPORT_LOCATION. Close OPM before -Apply.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SchemaDirectory,
    [ValidateSet('A1Trial','PipeClamp','Trunnion')][string]$Mode='A1Trial',
    [string]$BackupDirectory,
    [switch]$Apply
)
$ErrorActionPreference='Stop'
$className=switch($Mode){'A1Trial'{'SSP_A1_NATIVE_TEST'} 'PipeClamp'{'SSP_PIPE_CLAMP'} 'Trunnion'{'SSP_TRUNNION'}}
$componentName=if($Mode -eq 'A1Trial'){'A1NativeParametricComponent'}else{'NativePipeSupportComponent'}
$label=switch($Mode){'A1Trial'{'A1 Native Editing Trial'} 'PipeClamp'{'Pipe Clamp'} 'Trunnion'{'Pipe Trunnion'}}
$properties=@(@{Name='SSP_A1_DN';Type='int'},@{Name='SSP_A1_OPENING';Type='double'})
if($Mode -ne 'A1Trial'){$properties=@(@{Name='SSP_RECIPE';Type='string'})}
$directory=(Resolve-Path -LiteralPath $SchemaDirectory).ProviderPath
$names=@('OpenPlant_3D','OpenPlant_3D_Supplemental_Modeling','OpenPlant_3D_Supplemental_Isometrics_Isoextractor')
$plans=@()
function Child($doc,$parent,$name,$value,$namespace) {
    $node=$doc.CreateElement($name,$namespace)
    $node.InnerText=$value
    [void]$parent.AppendChild($node)
}
foreach($name in $names) {
    $path=Join-Path $directory ($name+'.01.08.ecschema.xml')
    $beforeHash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    $doc=New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace=$true
    $doc.Load($path)
    $root=$doc.DocumentElement
    if($root.LocalName -ne 'ECSchema' -or $root.GetAttribute('schemaName') -ne $name){throw "Wrong schema: $path"}
    $ecns=$root.NamespaceURI
    $ns=New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
    $ns.AddNamespace('ec',$ecns)
    $ns.AddNamespace('op','OpenPlant_CustomAttributes.08.11')
    $ns.AddNamespace('iso','OpenPlant_IsoExtractor_Custom_Attributes.01.08')
    $node=$doc.CreateElement('ECClass',$ecns)
    $node.SetAttribute('typeName',$className)
    $node.SetAttribute('isDomainClass',$(if($name -eq 'OpenPlant_3D'){'True'}else{'False'}))
    if($name -eq 'OpenPlant_3D') {
        if($null -eq $root.SelectSingleNode('ec:ECClass[@typeName="SUPPORT_LOCATION"]',$ns)){throw 'SUPPORT_LOCATION base class missing.'}
        $node.SetAttribute('displayLabel',$label)
        Child $doc $node 'BaseClass' 'SUPPORT_LOCATION' $ecns
        foreach($property in $properties) {
            $p=$doc.CreateElement('ECProperty',$ecns)
            $p.SetAttribute('propertyName',$property.Name); $p.SetAttribute('typeName',$property.Type)
            [void]$node.AppendChild($p)
        }
    } else {
        $attrs=$doc.CreateElement('ECCustomAttributes',$ecns)
        [void]$node.AppendChild($attrs)
        if($name -eq 'OpenPlant_3D_Supplemental_Modeling') {
            $creation=$root.SelectSingleNode('ec:ECClass[@typeName="SUPPORT_LOCATION"]/ec:ECCustomAttributes/op:CREATION_ATTRIBUTE',$ns)
            if($null -eq $creation){throw 'Stock SupportLocation creation attribute missing.'}
            $creation=$creation.CloneNode($true)
            foreach($entry in @(@('ASSEMBLY_NAME','SteelSectionProbe'),@('NAMESPACE','SteelSectionProbe'),@('CLASS_NAME',$componentName))) {
                $field=$creation.SelectSingleNode('op:'+$entry[0],$ns)
                if($null -eq $field){throw ('Creation attribute missing: '+$entry[0])}
                $field.InnerText=$entry[1]
            }
            if($creation.SelectSingleNode('op:HANDLER_TYPE',$ns).InnerText -ne 'Support'){throw 'Expected stock Support handler.'}
            [void]$attrs.AppendChild($creation)
        } else {
            $labels=$root.SelectSingleNode('ec:ECClass[@typeName="PLANT_BASE_OBJECT"]/ec:ECCustomAttributes/iso:BOM_LABELS',$ns)
            if($null -eq $labels){throw 'Default BOM labels missing.'}
            $labels=$labels.CloneNode($true)
            $tags=$labels.SelectNodes('iso:OTH_ATTRIBUTES/iso:BOM_ATTR_STRUCT[iso:NAME="IE_TAG"]/iso:ECX_VALUE',$ns)
            if($tags.Count -ne 1){throw 'IE_TAG is missing or ambiguous.'}
            $tags[0].InnerText='this.ALIAS'
            [void]$attrs.AppendChild($labels)
        }
    }
    $existing=$root.SelectSingleNode('ec:ECClass[@typeName="'+$className+'"]',$ns)
    if($null -ne $existing) {
        if($existing.OuterXml -ne $node.OuterXml){throw "Existing $className conflicts in $path; manual review required."}
        Write-Output "Already installed: $path"
        continue
    }
    [void]$root.AppendChild($doc.CreateWhitespace("`r`n    "))
    [void]$root.AppendChild($node)
    [void]$root.AppendChild($doc.CreateWhitespace("`r`n"))
    $plans+=@{Path=$path;Document=$doc;BeforeSHA256=$beforeHash}
    Write-Output ($path+"`r`n"+$node.OuterXml)
}
if(-not $Apply -or $plans.Count -eq 0){return}
if([string]::IsNullOrWhiteSpace($BackupDirectory)){throw '-Apply requires -BackupDirectory.'}
if(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(OpenPlantModeler|ustation)$' -and -not $_.HasExited }){throw 'Close OPM before installing trial schemas.'}
$backupRoot=[IO.Path]::GetFullPath($BackupDirectory)
[void][IO.Directory]::CreateDirectory($backupRoot)
$receipt=@()
try {
    # Prepare and validate every file before replacing any of them.
    foreach($plan in $plans) {
        $backup=Join-Path $backupRoot ([IO.Path]::GetFileName($plan.Path)+'.'+[Guid]::NewGuid().ToString('N')+'.bak')
        [IO.File]::Copy($plan.Path,$backup,$false)
        if((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $plan.BeforeSHA256){throw 'Backup hash mismatch.'}
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
        if((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.BeforeSHA256){throw 'Schema changed while preparing installation.'}
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
                if((Get-FileHash -LiteralPath $plan.Path -Algorithm SHA256).Hash -ne $plan.AfterSHA256){throw 'Schema changed after replacement; refusing to overwrite.'}
                [IO.File]::Copy($plan.Backup,$plan.Path,$true)
            } catch { $rollbackErrors+=$_.Exception.Message }
        }
    }
    if($rollbackErrors.Count){throw ($failure.Exception.Message+' Rollback incomplete: '+($rollbackErrors -join '; '))}
    throw $failure
} finally {
    foreach($plan in $plans){if($plan.Temporary -and [IO.File]::Exists($plan.Temporary)){[IO.File]::Delete($plan.Temporary)}}
}
$receiptPath=Join-Path $backupRoot ($className+'-'+[Guid]::NewGuid().ToString('N')+'.json')
$receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Output ('Installed '+$className+'. Receipt: '+$receiptPath)
