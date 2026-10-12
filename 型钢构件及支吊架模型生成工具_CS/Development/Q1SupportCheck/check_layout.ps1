param([string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
$pageFile = Join-Path $ProjectRoot 'UI/Q1Support/Q1SupportPage.xaml'
[xml]$markup = [IO.File]::ReadAllText($pageFile)
$markup.DocumentElement.RemoveAttribute('Class', 'http://schemas.microsoft.com/winfx/2006/xaml')
$markup.DocumentElement.RemoveAttribute('ClassModifier', 'http://schemas.microsoft.com/winfx/2006/xaml')
foreach ($node in $markup.SelectNodes('//*')) {
    foreach ($handler in @('Click','TextChanged','SelectionChanged','Checked','Unchecked')) { $node.RemoveAttribute($handler) }
    if ($node.LocalName -eq 'ResourceDictionary' -and $node.HasAttribute('Source')) {
        $node.SetAttribute('Source', ([uri](Join-Path $ProjectRoot 'UI/Themes/Theme.xaml')).AbsoluteUri)
    }
}
$page = [Windows.Markup.XamlReader]::Parse($markup.OuterXml)
$combo = $page.FindName('SmallDnCombo')
$combo.Items.Add('DN100 | 4″') | Out-Null
$combo.SelectedIndex = 0
$page.FindName('SpecificationText').Text = "子项 C · ∠100×10 · 允许荷载 3 kN`n类型 4 · 大管 DN900 / 小管 DN100 · H=1000 mm"
$page.FindName('PreviewText').Text = "预览：Q1-4-C-DN900-DN100-1000`n构件 A 长 1638 mm · 镜像"
$output = Join-Path $PSScriptRoot 'previews'
New-Item -ItemType Directory -Path $output -Force | Out-Null
foreach ($series in @(0,1)) {
    $page.FindName('SeriesCombo').SelectedIndex = $series
    $page.FindName('Q2Panel').Visibility = if($series -eq 1){[Windows.Visibility]::Visible}else{[Windows.Visibility]::Collapsed}
    $type = $page.FindName('TypeCombo')
    $type.Items.Clear()
    if($series -eq 1){
        $type.Items.Add('类型4 · 立管支撑立管') | Out-Null
        $page.FindName('DistanceLabel').Text = '两管中心间距 L（mm，最大1000）'
        $page.FindName('AngleButton').Visibility = [Windows.Visibility]::Visible
        $page.FindName('SpecificationText').Text = '子项 A · ∠50×6 · 允许荷载 0.2 kN'
        $page.FindName('PreviewText').Text = '预览：Q2-4-A-DN150-DN100-500'
    }else{$type.Items.Add('类型1 · 小管在下，两管垂直') | Out-Null}
    $type.SelectedIndex=0
foreach ($width in @(360,520,840)) {
    foreach ($height in @(420,650)) {
        $page.Measure([Windows.Size]::new($width,$height))
        $page.Arrange([Windows.Rect]::new(0,0,$width,$height))
        $page.UpdateLayout()
        foreach ($name in @('ConfirmButton')) {
            $button = $page.FindName($name)
            $position = $button.TranslatePoint([Windows.Point]::new(0,0),$page)
            if ($button.ActualWidth -lt 90 -or $position.Y -lt 0 -or
                $position.Y+$button.ActualHeight -gt $height+1) { throw "操作按钮越界：$name $width × $height" }
        }
        $bitmap = [Windows.Media.Imaging.RenderTargetBitmap]::new($width,$height,96,96,[Windows.Media.PixelFormats]::Pbgra32)
        $bitmap.Render($page)
        $encoder = [Windows.Media.Imaging.PngBitmapEncoder]::new()
        $encoder.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
        $stream = [IO.File]::Create((Join-Path $output "q$($series+1)-$width-$height.png"))
        try { $encoder.Save($stream) } finally { $stream.Dispose() }
    }
}
}
Write-Output 'Q1/Q2 WPF：360 / 520 / 840 px × 420 / 650 px 布局及固定操作区检查通过。'
