[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$projectName = '型钢构件及支吊架模型生成工具_CS'
$project = Join-Path $workspace $projectName
$archivePath = Join-Path $PSScriptRoot '迁移前源码及编译产物.zip'
$expected = 'C3E3C3E6D359FA351B47E68EE2BCCC3718AB9903A9E8C188C4FBF06787819204'
if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $expected) { throw 'Backup hash mismatch.' }
$files = @('Data/Home/HomeFeatureCatalog.cs','UI/WorkspaceView.xaml.cs',
    'SteelSupportModeler.csproj','Development/HomeCheck/Program.cs','README.md','AGENTS.md')
$directories = @('Domain/SquareManhole','Services/SquareManhole','Tools/SquareManhole','UI/SquareManhole','Development/SquareManholeCheck')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
try {
    $entries = @($archive.Entries | Where-Object {
        $_.FullName.StartsWith("$projectName/bin/Release/net48/") -and $_.Name.Length -gt 0
    })
    foreach ($file in $files) {
        $entry = $archive.GetEntry("$projectName/$file")
        if ($null -eq $entry) { throw "Missing backup entry: $file" }
        $entries += $entry
    }
    if (-not ($entries | Where-Object { $_.FullName.EndsWith('/SteelSectionProbe.dll') })) { throw 'Missing old DLL.' }
    # Validate destinations before any overwrite or directory move.
    foreach ($relative in (@($entries | ForEach-Object { $_.FullName }) + @($directories | ForEach-Object { "$projectName/$_" }))) {
        $target = [IO.Path]::GetFullPath((Join-Path $workspace $relative))
        if (-not $target.StartsWith($project + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
            throw "Target outside project: $target"
        }
    }
    if (-not $PSCmdlet.ShouldProcess($project,'Back up current state, restore old files and DLL, archive new modules')) { return }
    $run = Join-Path $PSScriptRoot ('回退前状态_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
    New-Item -ItemType Directory -Path $run | Out-Null
    Compress-Archive -LiteralPath $project -DestinationPath (Join-Path $run '当前工程.zip') -CompressionLevel Optimal
    foreach ($directory in $directories) {
        $source = [IO.Path]::GetFullPath((Join-Path $project $directory))
        $destination = [IO.Path]::GetFullPath((Join-Path $run $directory))
        if (-not $destination.StartsWith($run + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {
            throw "Move outside backup: $destination"
        }
        if (Test-Path -LiteralPath $source) {
            New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
            Move-Item -LiteralPath $source -Destination $destination
        }
    }
    foreach ($entry in $entries) {
        $target = [IO.Path]::GetFullPath((Join-Path $workspace $entry.FullName))
        New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$target,$true)
    }
    Write-Output "Rollback complete. Previous current state: $run"
} finally { $archive.Dispose() }
