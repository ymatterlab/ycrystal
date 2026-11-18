<#
.SYNOPSIS
Check that the packaged Ycrystal and an installation from source coexist on Windows.

.DESCRIPTION
For maintainers and CI. Uses the real Start menu and registry of the current user:

1. installs the packaged Ycrystal silently for the current user (-Setup);
2. adds the source installation's Start-menu entry (.venv\Scripts\ycrystal.exe
   --install-desktop, from -SourceRoot);
3. checks that the two shortcuts, application ids, and file types are separate, that the
   packaged program keeps opening .ycrystal files, and that the packaged program refuses
   --install-desktop;
4. removes the source entry (--uninstall-desktop) and checks that the packaged one is
   intact;
5. adds the source entry again, uninstalls the packaged Ycrystal, and checks that the
   source entry is intact.

At the end the packaged Ycrystal is uninstalled and the source entry is installed. Exit
status 0 when every check passed. Close Ycrystal windows before running it.

.PARAMETER Setup
The installer, Ycrystal-<version>-windows-x64-setup.exe.

.PARAMETER SourceRoot
A source folder with an installed .venv (scripts\install-windows.ps1); default: this
repository.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Setup,
    [string]$SourceRoot
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Continue"

if (-not $SourceRoot) { $SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
$sourcePython = Join-Path $SourceRoot ".venv\Scripts\python.exe"
$sourceYcrystal = Join-Path $SourceRoot ".venv\Scripts\ycrystal.exe"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{96A7291E-332A-4D2A-ACAD-E2489153A771}_is1"
$classes = "HKCU:\Software\Classes"
$failures = 0

function Assert([bool]$Condition, [string]$Text) {
    if ($Condition) { Write-Host "  ok    $Text" }
    else { Write-Host "  FAIL  $Text" -ForegroundColor Red; $script:failures++ }
}

function Get-Shortcut([string]$Name) {
    # Target, arguments, and application id, read with Ycrystal's own reader.
    $code = "import sys, json; from ycrystal.windows_shortcut import programs_folder, read_shortcut as r; " +
        "p = programs_folder() / sys.argv[1]; s = r(p) if p.is_file() else None; " +
        "print(json.dumps(None if s is None else {'target': s.target, 'arguments': s.arguments, 'app_id': s.app_id}))"
    $json = & $sourcePython -c $code $Name
    return ($json | ConvertFrom-Json)
}

function Get-Default([string]$Path) {
    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $item) { return $null }
    return $item.GetValue("")
}

function Test-OpenWith([string]$ProgId) {
    $item = Get-Item -LiteralPath "$classes\.ycrystal\OpenWithProgids" -ErrorAction SilentlyContinue
    return [bool]($item -and ($item.GetValueNames() -contains $ProgId))
}

function Install-Packaged {
    $log = Join-Path $env:TEMP "ycrystal-setup.log"
    Start-Process -FilePath $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/LOG=`"$log`"" -Wait
    $item = Get-ItemProperty $uninstallKey -ErrorAction SilentlyContinue
    if (-not $item) { Write-Host (Get-Content $log -Tail 20 | Out-String); throw "The packaged Ycrystal was not installed." }
    return $item.InstallLocation.TrimEnd("\")
}

function Uninstall-Packaged([string]$App) {
    # The uninstaller copies itself to the temporary folder and returns at once: wait
    # until its registry key is gone.
    Start-Process -FilePath (Join-Path $App "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait
    for ($i = 0; $i -lt 120 -and (Test-Path $uninstallKey); $i++) { Start-Sleep -Milliseconds 500 }
    if (Test-Path $uninstallKey) { throw "The packaged Ycrystal was not uninstalled." }
}

function Assert-Packaged([string]$App) {
    $shortcut = Get-Shortcut "Ycrystal.lnk"
    Assert ($null -ne $shortcut -and $shortcut.target -eq (Join-Path $App "Ycrystal.exe")) "packaged shortcut 'Ycrystal' starts $App\Ycrystal.exe"
    Assert ($null -ne $shortcut -and $shortcut.app_id -eq "YMatterLab.Ycrystal.App") "packaged shortcut has id YMatterLab.Ycrystal.App"
    Assert (Test-Path "$classes\YMatterLab.Ycrystal.Project\shell\open\command") "packaged file type YMatterLab.Ycrystal.Project registered"
    Assert (Test-OpenWith "YMatterLab.Ycrystal.Project") "packaged file type in the Open with list"
}

function Assert-Source {
    $shortcut = Get-Shortcut "Ycrystal (development).lnk"
    Assert ($null -ne $shortcut -and $shortcut.target -like "*\.venv\Scripts\pythonw.exe") "source shortcut 'Ycrystal (development)' starts .venv\Scripts\pythonw.exe"
    Assert ($null -ne $shortcut -and $shortcut.app_id -eq "YMatterLab.Ycrystal") "source shortcut has id YMatterLab.Ycrystal"
    Assert (Test-Path "$classes\Ycrystal.Project\shell\open\command") "source file type Ycrystal.Project registered"
    Assert (Test-OpenWith "Ycrystal.Project") "source file type in the Open with list"
}

Write-Host "Packaged installer: $Setup"
Write-Host "Source installation: $SourceRoot"
if (-not (Test-Path $sourceYcrystal)) { throw "No source installation in $SourceRoot (run scripts\install-windows.ps1)." }

Write-Host ""
Write-Host "1. Packaged Ycrystal installed first, then the source entry"
$app = Install-Packaged
& $sourceYcrystal --install-desktop | Out-Null
Assert ($LASTEXITCODE -eq 0) "source --install-desktop succeeded"
Assert-Packaged $app
Assert-Source
Assert ((Get-Default "$classes\.ycrystal") -eq "YMatterLab.Ycrystal.Project") ".ycrystal still opens with the packaged Ycrystal"
$cli = Join-Path $app "ycrystal-cli.exe"
$reported = "$(& $cli --version)".Trim()
Assert ($reported -like "ycrystal *") "ycrystal-cli.exe --version: $reported"
& $cli --install-desktop 2>&1 | Out-Null
Assert ($LASTEXITCODE -eq 1) "the packaged program refuses --install-desktop"

Write-Host ""
Write-Host "2. Source entry uninstalled: the packaged Ycrystal stays"
& $sourceYcrystal --uninstall-desktop | Out-Null
Assert-Packaged $app
Assert ($null -eq (Get-Shortcut "Ycrystal (development).lnk")) "source shortcut removed"
Assert (-not (Test-Path "$classes\Ycrystal.Project")) "source file type removed"
Assert ((Get-Default "$classes\.ycrystal") -eq "YMatterLab.Ycrystal.Project") ".ycrystal still opens with the packaged Ycrystal"

Write-Host ""
Write-Host "3. Packaged Ycrystal uninstalled: the source entry stays"
& $sourceYcrystal --install-desktop | Out-Null
Uninstall-Packaged $app
Assert-Source
Assert ($null -eq (Get-Shortcut "Ycrystal.lnk")) "packaged shortcut removed"
Assert (-not (Test-Path "$classes\YMatterLab.Ycrystal.Project")) "packaged file type removed"
Assert ((Get-Default "$classes\.ycrystal") -ne "YMatterLab.Ycrystal.Project") ".ycrystal no longer names the packaged file type"
Assert (-not (Test-Path (Join-Path $app "Ycrystal.exe"))) "packaged program files removed"

Write-Host ""
if ($failures -gt 0) { Write-Host "$failures check(s) failed." -ForegroundColor Red; exit 1 }
Write-Host "All checks passed." -ForegroundColor Green
exit 0
