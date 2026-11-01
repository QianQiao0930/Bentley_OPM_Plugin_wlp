param(
    [string]$SchemaDirectory='C:\ProgramData\Bentley\OpenPlant 2024\Configuration\WorkSpaces\CINF_International_Projects_Workspace\WorkSets\CINF_F1263AA\Standards\OpenPlant\Schemas',
    [string]$OutputPath=(Join-Path $PSScriptRoot 'handwheel-contract.json')
)
# Disk XML only. Does not start Bentley, load a DGN, or modify a schema.
$ErrorActionPreference='Stop'
$taskBasePath=Join-Path $SchemaDirectory 'OpenPlant_3D.01.08.ecschema.xml'
$taskModelingPath=Join-Path $SchemaDirectory 'OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml'
[xml]$taskBase=Get-Content -LiteralPath $taskBasePath -Raw -Encoding UTF8
[xml]$taskModeling=Get-Content -LiteralPath $taskModelingPath -Raw -Encoding UTF8
$taskWheel=$taskBase.SelectSingleNode('//*[@typeName="HAND_WHEEL"]')
$taskManual=$taskBase.SelectSingleNode('//*[@typeName="MANUAL_VALVE_OPERATING_DEVICE"]')
$taskActuator=$taskBase.SelectSingleNode('//*[@typeName="VALVE_ACTUATOR"]')
$taskRelation=$taskBase.SelectSingleNode('//*[local-name()="ECRelationshipClass" and @typeName="VALVE_HAS_VALVE_OPERATING_DEVICE"]')
$taskWheelModeling=$taskModeling.SelectSingleNode('//*[@typeName="HAND_WHEEL"]')
$taskCreation=$taskWheelModeling.SelectSingleNode('.//*[local-name()="CREATION_ATTRIBUTE"]')
$taskChecks=[ordered]@{
    HandwheelInheritsManual=(@($taskWheel.BaseClass) -contains 'MANUAL_VALVE_OPERATING_DEVICE')
    ManualInheritsOperatingDevice=(@($taskManual.BaseClass) -contains 'VALVE_OPERATING_DEVICE')
    ManualHasBinaryGeometry=($null -ne $taskManual.SelectSingleNode('./*[local-name()="ECProperty" and @propertyName="Geometry" and @typeName="binary"]'))
    ActuatorAlsoHasBinaryGeometry=($null -ne $taskActuator.SelectSingleNode('./*[local-name()="ECProperty" and @propertyName="Geometry" and @typeName="binary"]'))
    HandwheelHandler=($taskCreation.CLASS_NAME -eq 'Handwheel')
    HandwheelHandlerNamespace=($taskCreation.NAMESPACE -eq 'Bentley.Building.Mechanical.ComponentLibrary.ValveOperator')
    TopworkHandlerType=($taskCreation.HANDLER_TYPE -eq 'Topwork')
    NativePlacementTool=($taskCreation.PLACEMENT_TOOL -eq 'TopworksPlacementTool')
    RelationshipExists=($null -ne $taskRelation)
    EmbeddingForward=($taskRelation.strength -eq 'embedding' -and $taskRelation.strengthDirection -eq 'forward')
    SourcePipingComponent=($taskRelation.Source.Class.class -eq 'PIPING_COMPONENT')
    TargetOperatingDevice=($taskRelation.Target.Class.class -eq 'VALVE_OPERATING_DEVICE')
    RelationshipCardinality=($taskRelation.Source.cardinality -eq '(0,1)' -and $taskRelation.Target.cardinality -eq '(0,1)')
}
$taskReport=[ordered]@{
    InspectedUtc=[DateTime]::UtcNow.ToString('o')
    EvidenceScope='Disk schema only; not the active host or embedded DGN schema; not runtime acceptance.'
    BaseSchema=$taskBasePath; BaseSha256=(Get-FileHash -LiteralPath $taskBasePath -Algorithm SHA256).Hash
    ModelingSchema=$taskModelingPath; ModelingSha256=(Get-FileHash -LiteralPath $taskModelingPath -Algorithm SHA256).Hash
    Checks=$taskChecks; Passed=(@($taskChecks.Values | Where-Object {-not $_}).Count -eq 0)
    HandwheelBaseXml=$taskWheel.OuterXml; ManualBaseXml=$taskManual.OuterXml
    HandwheelModelingXml=$taskWheelModeling.OuterXml; RelationshipXml=$taskRelation.OuterXml
}
$taskReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output ('ContractChecks='+$taskChecks.Count+'; Passed='+$taskReport.Passed)
if(-not $taskReport.Passed){throw 'Disk handwheel contract differs; inspect the saved evidence.'}
