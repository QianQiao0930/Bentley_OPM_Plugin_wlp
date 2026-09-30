$ErrorActionPreference='Stop'
Add-Type -AssemblyName PresentationFramework,PresentationCore,WindowsBase,System.Xaml
$taskSdk='C:\Program Files\Bentley\OpenPlant 2024\IsometricsManager'
$taskRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskDll=Join-Path $taskRoot 'bin\Release\net48\SteelSectionProbe.dll'
$taskResolver=[ResolveEventHandler]{param($sender,$eventArgs)
 $taskName=([Reflection.AssemblyName]$eventArgs.Name).Name+'.dll'
 foreach($taskDir in @($taskSdk,(Join-Path $taskSdk 'Assemblies'),(Join-Path $taskSdk 'Assemblies\ECFramework'))){
  $taskCandidate=Join-Path $taskDir $taskName
  if(Test-Path -LiteralPath $taskCandidate){return [Reflection.Assembly]::LoadFrom($taskCandidate)}
 }
 return $null
}
[AppDomain]::CurrentDomain.add_AssemblyResolve($taskResolver)
$taskAssembly=[Reflection.Assembly]::LoadFrom($taskDll)
$taskPage=[Activator]::CreateInstance($taskAssembly.GetType('SteelSectionProbe.HandrailPage'),[Reflection.BindingFlags]'Instance,NonPublic',$null,@(),$null)
$taskPage.Width=520;$taskPage.Height=520
$taskPage.Measure([Windows.Size]::new(520,520))
$taskPage.Arrange([Windows.Rect]::new(0,0,520,520))
$taskPage.UpdateLayout()
$taskBitmap=[Windows.Media.Imaging.RenderTargetBitmap]::new(520,520,96,96,[Windows.Media.PixelFormats]::Pbgra32)
$taskBitmap.Render($taskPage)
$taskEncoder=[Windows.Media.Imaging.PngBitmapEncoder]::new()
$taskEncoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($taskBitmap))
$taskOutput=Join-Path $PSScriptRoot 'page-preview.png'
$taskStream=[IO.File]::Create($taskOutput)
try{$taskEncoder.Save($taskStream)}finally{$taskStream.Dispose()}
Write-Output $taskOutput
