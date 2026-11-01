param(
    [Parameter(Mandatory=$true)][string]$SourceSchemaDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('HAND_WHEEL','GEARBOX_OPERATOR')][string]$BaseClassName='HAND_WHEEL',
    [switch]$SelectableCel
)
# Preparation only: never modifies the supplied workspace schemas or starts OPM.
$ErrorActionPreference='Stop'
$taskSource=(Resolve-Path -LiteralPath $SourceSchemaDirectory).Path
$taskOutput=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $taskOutput){throw 'Output directory already exists. Use a new directory to preserve prior evidence.'}
if($taskOutput.StartsWith($taskSource+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Prepare outside the source schema directory.'
}
$taskNames=@('OpenPlant_3D.01.08.ecschema.xml','OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml')
$taskClassName='SSP_CEL_'+$BaseClassName
$taskHandler=if($BaseClassName -eq 'GEARBOX_OPERATOR'){'CelGearboxComponent'}else{'CelHandwheelComponent'}
$taskAssembly='ValveActuatorCallbackCheck';$taskNamespace='ActuatorCallbackCheck'
if($SelectableCel){
    if($BaseClassName -ne 'GEARBOX_OPERATOR'){throw 'SelectableCel requires GEARBOX_OPERATOR.'}
    $taskClassName='SSP_CEL_VALVE_ACTUATOR';$taskHandler='CelValveActuatorComponent'
    $taskAssembly='SteelSectionProbe';$taskNamespace='SteelSectionProbe'
}
$taskPlans=@()
foreach($taskName in $taskNames){
    $taskPath=Join-Path $taskSource $taskName
    $taskDocument=New-Object System.Xml.XmlDocument
    $taskDocument.PreserveWhitespace=$true
    $taskDocument.Load($taskPath)
    $taskRoot=$taskDocument.DocumentElement
    $taskEcNamespace=$taskRoot.NamespaceURI
    if($null -ne $taskRoot.SelectSingleNode('*[@typeName="'+$taskClassName+'"]')){throw 'Source already contains the requested test class; do not overwrite it.'}
    $taskWheel=$taskRoot.SelectSingleNode('*[@typeName="'+$BaseClassName+'"]')
    if($null -eq $taskWheel){throw ($BaseClassName+' missing in '+$taskName)}
    $taskBeforeWheel=$taskWheel.OuterXml
    $taskBeforeNodes=@($taskRoot.ChildNodes | ForEach-Object {$_.OuterXml})
    $taskNode=$taskDocument.CreateElement('ECClass',$taskEcNamespace)
    $taskNode.SetAttribute('typeName',$taskClassName)
    if($taskName -eq $taskNames[0]){
        $taskNode.SetAttribute('isDomainClass','True');$taskNode.SetAttribute('displayLabel',('CEL '+$BaseClassName+' Callback Check'))
        $taskBase=$taskDocument.CreateElement('BaseClass',$taskEcNamespace);$taskBase.InnerText=$BaseClassName;[void]$taskNode.AppendChild($taskBase)
        $taskProperty=$taskDocument.CreateElement('ECProperty',$taskEcNamespace)
        $taskProperty.SetAttribute('propertyName','SSP_CEL_VERSION');$taskProperty.SetAttribute('typeName','int');[void]$taskNode.AppendChild($taskProperty)
        if($SelectableCel){
            foreach($taskPropertyName in @('SSP_CEL_NAME','SSP_CEL_SOURCE','SSP_CEL_SHA256','SSP_CEL_DATA','SSP_CEL_TOKEN')){
                $taskProperty=$taskDocument.CreateElement('ECProperty',$taskEcNamespace)
                $taskProperty.SetAttribute('propertyName',$taskPropertyName)
                $taskProperty.SetAttribute('typeName',$(if($taskPropertyName -eq 'SSP_CEL_DATA'){'binary'}else{'string'}))
                [void]$taskNode.AppendChild($taskProperty)
            }
        }
    }else{
        $taskNode.SetAttribute('isDomainClass','False')
        $taskAttributes=$taskDocument.CreateElement('ECCustomAttributes',$taskEcNamespace);[void]$taskNode.AppendChild($taskAttributes)
        $taskCreation=$taskWheel.SelectSingleNode('.//*[local-name()="CREATION_ATTRIBUTE"]')
        if($null -eq $taskCreation){throw ($BaseClassName+' creation attribute missing.')}
        $taskCreation=$taskCreation.CloneNode($true)
        $taskValues=[ordered]@{ASSEMBLY_NAME=$taskAssembly;NAMESPACE=$taskNamespace;CLASS_NAME=$taskHandler}
        foreach($taskKey in $taskValues.Keys){
            $taskField=$taskCreation.SelectSingleNode('*[local-name()="'+$taskKey+'"]')
            if($null -eq $taskField){throw ('Missing creation field '+$taskKey)}
            $taskField.InnerText=$taskValues[$taskKey]
        }
        if($taskCreation.SelectSingleNode('*[local-name()="HANDLER_TYPE"]').InnerText -ne 'Topwork' -or
            $taskCreation.SelectSingleNode('*[local-name()="PLACEMENT_TOOL"]').InnerText -ne 'TopworksPlacementTool'){
            throw 'Source is not the expected native Topwork/TopworksPlacementTool contract.'
        }
        [void]$taskAttributes.AppendChild($taskCreation)
    }
    [void]$taskRoot.AppendChild($taskNode)
    if($taskWheel.OuterXml -cne $taskBeforeWheel){throw ('Existing '+$BaseClassName+' changed.')}
    $taskAfterNodes=@($taskRoot.ChildNodes | Where-Object {$_ -ne $taskNode} | ForEach-Object {$_.OuterXml})
    if(($taskBeforeNodes -join "`n") -cne ($taskAfterNodes -join "`n")){throw 'An existing schema node changed.'}
    $taskPlans+=,[pscustomobject]@{Name=$taskName;Source=$taskPath;SourceSha256=(Get-FileHash -LiteralPath $taskPath).Hash;
        Document=$taskDocument;TestClassXml=$taskNode.OuterXml;ExistingBaseClassUnchanged=$true;ExistingNodesUnchanged=$true}
}
New-Item -ItemType Directory -Path $taskOutput | Out-Null
$taskReceipt=@()
foreach($taskPlan in $taskPlans){
    $taskTarget=Join-Path $taskOutput $taskPlan.Name
    $taskPlan.Document.Save($taskTarget)
    $taskReopened=New-Object System.Xml.XmlDocument
    $taskReopened.PreserveWhitespace=$true
    $taskReopened.Load($taskTarget)
    $taskNewNode=$taskReopened.DocumentElement.SelectSingleNode('*[@typeName="'+$taskClassName+'"]')
    if($null -eq $taskNewNode -or $taskNewNode.OuterXml -cne $taskPlan.TestClassXml){throw 'Prepared file failed XML reread.'}
    $taskOriginalDocument=New-Object System.Xml.XmlDocument
    $taskOriginalDocument.PreserveWhitespace=$true
    $taskOriginalDocument.Load($taskPlan.Source)
    $taskRoundtripNodes=@($taskReopened.DocumentElement.ChildNodes | Where-Object {$_ -ne $taskNewNode} | ForEach-Object {$_.OuterXml})
    $taskOriginalNodes=@($taskOriginalDocument.DocumentElement.ChildNodes | ForEach-Object {$_.OuterXml})
    if(($taskRoundtripNodes -join "`n") -cne ($taskOriginalNodes -join "`n")){throw 'An existing schema node changed after XML roundtrip.'}
    if((Get-FileHash -LiteralPath $taskPlan.Source).Hash -cne $taskPlan.SourceSha256){throw 'Source schema changed during preparation.'}
    $taskReceipt+=,[ordered]@{Name=$taskPlan.Name;Source=$taskPlan.Source;SourceSha256=$taskPlan.SourceSha256;
        Prepared=$taskTarget;PreparedSha256=(Get-FileHash -LiteralPath $taskTarget).Hash;
        ExistingBaseClassUnchanged=$taskPlan.ExistingBaseClassUnchanged;ExistingNodesUnchanged=$taskPlan.ExistingNodesUnchanged;
        TestClassXml=$taskPlan.TestClassXml}
}
[ordered]@{PreparedUtc=[DateTime]::UtcNow.ToString('o');Applied=$false;HostStarted=$false;TestClass=$taskClassName;BaseClass=$BaseClassName;Handler=$taskHandler;Assembly=$taskAssembly;Namespace=$taskNamespace;SelectableCel=$SelectableCel.IsPresent;Files=$taskReceipt} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskOutput 'preparation-receipt.json') -Encoding UTF8
Write-Output ('PreparedOnly='+$taskOutput+'; Existing schemas unchanged; Applied=false')
