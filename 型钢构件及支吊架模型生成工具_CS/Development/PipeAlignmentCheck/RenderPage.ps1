param([int]$PanelWidth=480)
Add-Type -AssemblyName PresentationFramework,PresentationCore,WindowsBase
$basePath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$xamlPath = Join-Path $basePath 'UI/PipeAlignment/PipeAlignmentPage.xaml'
$themePath = Join-Path $basePath 'UI/Themes/Theme.xaml'
$pageXml = [IO.File]::ReadAllText($xamlPath)
$pageXml = $pageXml -replace 'x:Class="[^"]*"|x:ClassModifier="[^"]*"',''
$pageXml = $pageXml -replace '(?<!Is)(Checked|Unchecked|Click|TextChanged)="[^"]*"',''
$pageXml = $pageXml.Replace('../Themes/Theme.xaml',([Uri]$themePath).AbsoluteUri)
$reader = [Xml.XmlReader]::Create([IO.StringReader]::new($pageXml))
$view = [Windows.Markup.XamlReader]::Load($reader)
$view.FindName('ReferenceText').Text="4002-MP-FLW-0020-A1B-150-NI`nPIPE · 外径168.3 mm · 保温0.0 mm`n读取正常"
$view.FindName('BottomRadio').IsChecked=$true
$view.FindName('PipeSurface').IsChecked=$true
$view.FindName('ZScope').IsChecked=$true
$view.FindName('CountText').Text='已选 2 根'
$view.FindName('SummaryText').Text='基准标高984.63 mm · 将移动1，已对齐1'
$view.FindName('StatusText').Text='选择基准管和目标管 → 自动预览 → 应用'
$rows = @()
foreach($i in 1..3){$rows += [pscustomobject]@{Name='4002-MP-FLW-0020-A1B-150-NI';Connection='PIPE · 两端连接';Current='当前984.63';Target='目标1068.78';Delta='ΔZ +84.15';Status='外径114.3 mm · 将移动';StatusBrush=[Windows.Media.Brushes]::DarkGoldenrod;Details='示例数据'}}
$view.FindName('PipeList').ItemsSource=$rows
$view.Width=$PanelWidth;$view.Height=960
$view.Measure([Windows.Size]::new($PanelWidth,960));$view.Arrange([Windows.Rect]::new(0,0,$PanelWidth,960));$view.UpdateLayout()
$bitmap=[Windows.Media.Imaging.RenderTargetBitmap]::new($PanelWidth,960,96,96,[Windows.Media.PixelFormats]::Pbgra32)
$bitmap.Render($view)
$encoder=[Windows.Media.Imaging.PngBitmapEncoder]::new();$encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
$stream=[IO.File]::Create((Join-Path $PSScriptRoot 'WpfPage.png'));$encoder.Save($stream);$stream.Dispose()
