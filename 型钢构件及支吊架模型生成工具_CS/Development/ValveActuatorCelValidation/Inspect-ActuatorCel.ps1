param(
    [Parameter(Mandatory=$true)][string]$SourcePath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$BentleyRoot='D:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler'
)
# Run with Windows PowerShell 5.1 -STA. Only opens the library for program, read-only.
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding $false
$taskSource=(Resolve-Path -LiteralPath $SourcePath).Path
$taskOutput=[IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskHash=(Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash
$taskInterop=Join-Path $BentleyRoot 'Assemblies\Bentley.Interop.MicroStationDGN.dll'
Add-Type -Path $taskInterop
Add-Type -ReferencedAssemblies $taskInterop -TypeDefinition @'
using System;
using System.Collections.Generic;
using Com = Bentley.Interop.MicroStationDGN;
public static class ActuatorCelReadOnly
{
    public class UnitInfo {
        public string Label, Base, System;
        public double Numerator, Denominator;
    }
    public class Item {
        public string Id, Type, CellName;
        public bool Graphical, SmartSolid, SharedCell, SharedDefinition;
        public int Color, Depth;
        public double[] Low, High;
    }
    public class ModelInfo {
        public string Name, Description;
        public bool Is3D, Placeable, Annotation;
        public string CellType;
        public int Attachments, RootCount;
        public double UorPerMaster, UorPerStorage;
        public double[] GlobalOrigin, Low, High;
        public UnitInfo MasterUnit, StorageUnit;
        public List<Item> Items = new List<Item>();
    }
    static double[] P(Com.Point3d p) { return new double[] {p.X,p.Y,p.Z}; }
    static UnitInfo U(Com.MeasurementUnit u) {
        return new UnitInfo {Label=u.Label, Base=u.Base.ToString(), System=u.System.ToString(),
            Numerator=u.UnitsPerBaseNumerator, Denominator=u.UnitsPerBaseDenominator};
    }
    static void Walk(Com.Element e, int depth, List<Item> items) {
        if(depth>64 || items.Count>=20000) throw new InvalidOperationException("CEL hierarchy limit exceeded.");
        var item=new Item {Id=e.ID64.ToString(), Type=e.Type.ToString(), Depth=depth,
            Graphical=e.IsGraphical, SmartSolid=e.IsSmartSolidElement,
            SharedCell=e.IsSharedCellElement(), SharedDefinition=e.IsSharedCellDefinitionElement()};
        if(item.Graphical) { var r=e.Range; item.Low=P(r.Low); item.High=P(r.High); item.Color=e.Color; }
        items.Add(item);
        // A SmartSolid is atomic: never enumerate kernel/display storage records.
        if(item.SmartSolid || item.SharedCell || item.SharedDefinition) return;
        if(e.IsCellElement()) {
            var cell=e.AsCellElement(); item.CellName=cell.Name;
            var children=cell.GetSubElements();
            while(children.MoveNext()) Walk(children.Current,depth+1,items);
        } else if(e.IsComplexElement() && (e.Type==Com.MsdElementType.ComplexString || e.Type==Com.MsdElementType.ComplexShape)) {
            var children=e.AsComplexElement().GetSubElements();
            while(children.MoveNext()) Walk(children.Current,depth+1,items);
        }
    }
    public static double[] Calibration(object appObject) {
        var app=(Com.Application)appObject;
        var a=new Com.Point3d(); var b=new Com.Point3d {X=1};
        var line=app.CreateLineElement2(null,ref a,ref b);
        var r=line.Range;
        return new double[] {r.High.X-r.Low.X,app.ActiveModelReference.UORsPerMasterUnit};
    }
    public static ModelInfo[] Read(object fileObject) {
        var file=(Com.DesignFile)fileObject;
        var result=new List<ModelInfo>();
        foreach(Com.ModelReference model in file.Models) {
            var info=new ModelInfo {Name=model.Name, Description=model.Description,
                Is3D=model.Is3D, Placeable=model.CanBePlacedAsCell, Annotation=model.CanBePlacedAsAnnotationCell,
                CellType=model.CellType.ToString(), UorPerMaster=model.UORsPerMasterUnit,
                UorPerStorage=model.UORsPerStorageUnit, GlobalOrigin=P(model.GlobalOrigin),
                MasterUnit=U(model.get_MasterUnit()), StorageUnit=U(model.get_StorageUnit()),
                Attachments=model.Attachments.Count};
            var scan=model.Scan(null);
            while(scan.MoveNext()) {info.RootCount++; Walk(scan.Current,0,info.Items);}
            if(info.Items.Exists(i=>i.Graphical)) {var r=model.Range(false); info.Low=P(r.Low); info.High=P(r.High);}
            result.Add(info);
        }
        return result.ToArray();
    }
}
'@
$taskReport=[ordered]@{StartedUtc=[DateTime]::UtcNow.ToString('o'); SourcePath=$taskSource;
    SourceSha256Before=$taskHash; SourceBytes=(Get-Item -LiteralPath $taskSource).Length;
    Executable=Join-Path $BentleyRoot 'OpenPlantModeler.exe'; Status='Running'; Models=@()}
$taskApp=$null
$taskFile=$null
$taskCreated=$false
$taskMayQuit=$false
$taskOwnContext=$false
try {
    # Failure to find a running automation object is expected when the host is closed.
    try {$taskApp=[Runtime.InteropServices.Marshal]::GetActiveObject('MicroStationDGN.Application')} catch [Runtime.InteropServices.COMException] {}
    if($null -eq $taskApp) {
        Write-Output 'Starting isolated Bentley automation (no design model writes).'
        $taskProcess=Start-Process -FilePath $taskReport.Executable -ArgumentList '/Automation' -WindowStyle Hidden -PassThru
        $taskReport.StartedProcessId=$taskProcess.Id
        $taskDeadline=[DateTime]::UtcNow.AddSeconds(50)
        while($null -eq $taskApp -and [DateTime]::UtcNow -lt $taskDeadline) {
            Start-Sleep -Milliseconds 500
            try {$taskApp=[Runtime.InteropServices.Marshal]::GetActiveObject('MicroStationDGN.Application')} catch [Runtime.InteropServices.COMException] {}
        }
        if($null -eq $taskApp) {throw 'Bentley automation was unavailable after 50 seconds; no CEL was opened.'}
        $taskCreated=$true
        $taskMayQuit=-not $taskApp.HasActiveDesignFile
    }
    $taskReport.HostVersion=[string]$taskApp.Version
    $taskReport.HadActiveFile=[bool]$taskApp.HasActiveDesignFile
    $taskReport.ActiveFileBefore=if($taskApp.HasActiveDesignFile){[string]$taskApp.ActiveDesignFile.FullName}else{$null}
    # COM coordinate conversion depends on the active model. Without one, ranges
    # can be returned in raw UORs. Use a read-only scratch copy as the context.
    if(-not $taskApp.HasActiveDesignFile) {
        $taskContext=Join-Path $taskOutput 'coordinate-context.dgn'
        if(Test-Path -LiteralPath $taskContext){throw 'Scratch context already exists; use a new output directory.'}
        Copy-Item -LiteralPath $taskSource -Destination $taskContext
        $taskApp.OpenDesignFile($taskContext,$true) | Out-Null
        $taskOwnContext=$true
        $taskReport.ScratchContext=$taskContext
    }
    $taskReport.CoordinateContextPath=[string]$taskApp.ActiveDesignFile.FullName
    $taskReport.CoordinateContextModel=[string]$taskApp.ActiveModelReference.Name
    $taskReport.CoordinateContextMasterLabel=[string]$taskApp.ActiveModelReference.MasterUnit.Label
    $taskReport.OrphanLineCalibration=@([ActuatorCelReadOnly]::Calibration($taskApp))
    if($taskApp.HasActiveDesignFile -and [string]::Equals($taskApp.ActiveDesignFile.FullName,$taskSource,[StringComparison]::OrdinalIgnoreCase)) {
        # The existing active document belongs to the user; never close it.
        $taskReport.Models=@([ActuatorCelReadOnly]::Read($taskApp.ActiveDesignFile))
    } else {
        $taskFile=$taskApp.OpenDesignFileForProgram($taskSource,$true)
        $taskReport.Models=@([ActuatorCelReadOnly]::Read($taskFile))
        $taskFile.Close()
        $taskFile=$null
    }
    $taskReport.ActiveFileAfter=if($taskApp.HasActiveDesignFile){[string]$taskApp.ActiveDesignFile.FullName}else{$null}
    if($taskReport.CoordinateContextPath -cne $taskReport.ActiveFileAfter){throw 'The coordinate context changed during the read-only inspection.'}
    $taskReport.Status='ReadOnlyInspectionPassed'
} catch {
    $taskReport.Status='Failed'
    $taskReport.Error=$_.Exception.ToString()
    $taskReport.ScriptStack=$_.ScriptStackTrace
    Write-Output $taskReport.Error
} finally {
    if($null -ne $taskFile){try{$taskFile.Close()}catch{$taskReport.CloseError=$_.Exception.ToString();$taskReport.Status='Failed'}}
    if($taskOwnContext -and $null -ne $taskApp -and $taskApp.HasActiveDesignFile -and [string]::Equals($taskApp.ActiveDesignFile.FullName,$taskContext,[StringComparison]::OrdinalIgnoreCase)){
        try{$taskApp.ActiveDesignFile.Close();$taskReport.ScratchContextClosed=$true}catch{$taskReport.ContextCloseError=$_.Exception.ToString();$taskReport.Status='Failed'}
    }
    $taskReport.SourceSha256After=(Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash
    if($taskReport.SourceSha256After -cne $taskHash){$taskReport.Status='Failed';$taskReport.SourceChanged=$true}
    if($taskCreated -and $taskMayQuit -and $null -ne $taskApp -and -not $taskApp.HasActiveDesignFile){
        try{$taskApp.Quit();$taskReport.OwnAutomationClosed=$true}catch{$taskReport.QuitError=$_.Exception.ToString()}
    }
    $taskReport.FinishedUtc=[DateTime]::UtcNow.ToString('o')
    $taskReport | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path $taskOutput 'cel-native-inventory.json') -Encoding UTF8
}
Write-Output ('Status='+$taskReport.Status)
Write-Output ('Evidence='+ (Join-Path $taskOutput 'cel-native-inventory.json'))
if($taskReport.Status -eq 'Failed'){exit 1}
