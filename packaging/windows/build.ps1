<#
.SYNOPSIS
Build the packaged Ycrystal for Windows and its graphical installer.

.DESCRIPTION
For maintainers. Run it in PowerShell, from anywhere in the repository:

    powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1

It needs Python 3.12 ("py -3.12", or -Python) and, for the installer, Inno Setup 6
(winget install --id JRSoftware.InnoSetup --exact). In order:

1. a build environment build\windows\venv: Ycrystal installed from this folder (not
   editable) with the pins of constraints.txt, and the build tools pinned in
   packaging\windows\requirements.txt (PyInstaller);
2. the icon build\windows\ycrystal.ico, drawn from the SVG icon;
3. PyInstaller (packaging\windows\ycrystal.spec): dist\windows\Ycrystal\ with
   Ycrystal.exe (the window) and ycrystal-cli.exe (the command line);
4. a check that ycrystal-cli.exe starts and reports this version;
5. Inno Setup (packaging\windows\ycrystal.iss):
   dist\windows\Ycrystal-<version>-windows-x64-setup.exe.

The build environment is kept for the next build; -Clean recreates it. Nothing outside
build\ and dist\ is written, and the developer installation (.venv, its Start-menu
entry) is not touched.

.PARAMETER Python
The Python interpreter for the build environment, instead of "py -3.12". The packaged
program contains this Python.

.PARAMETER Clean
Recreate the build environment, and remove earlier PyInstaller output.

.PARAMETER NoInstaller
Stop after PyInstaller and the check (no Inno Setup needed).
#>
[CmdletBinding()]
param(
    [string]$Python,
    [switch]$Clean,
    [switch]$NoInstaller
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Continue"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$build = Join-Path $root "build\windows"
$dist = Join-Path $root "dist\windows"
$venv = Join-Path $build "venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$bundle = Join-Path $dist "Ycrystal"
$icon = Join-Path $build "ycrystal.ico"

function Write-Step([string]$Text) { Write-Host ""; Write-Host "==> $Text" -ForegroundColor Cyan }
function Stop-Build([string]$Text) { Write-Host ""; Write-Host "ERROR: $Text" -ForegroundColor Red; exit 1 }

function Find-InnoCompiler {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    # Inno Setup records its folder under its uninstall key (per user or per computer).
    $keys = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    )
    foreach ($key in $keys) {
        $item = Get-ItemProperty $key -ErrorAction SilentlyContinue
        if ($item -and $item.PSObject.Properties["InstallLocation"]) {
            $candidate = Join-Path $item.InstallLocation "ISCC.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    return $null
}

Set-Location $root
Write-Host "Building the packaged Ycrystal from $root"

# ----- 1. Build environment ----------------------------------------------------------------
Write-Step "Build environment $venv"
if ($Clean) {
    foreach ($folder in $venv, (Join-Path $build "pyinstaller"), $bundle) {
        if (Test-Path $folder) { Remove-Item -Recurse -Force -LiteralPath $folder }
    }
}
if (-not (Test-Path $venvPython)) {
    if (-not $Python) {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if (-not $launcher) { Stop-Build "Python 3.12 was not found: install it, or give -Python." }
        $Python = "$(& $launcher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null)".Trim()
        if ($LASTEXITCODE -ne 0 -or -not $Python) { Stop-Build "Python 3.12 was not found: install it, or give -Python." }
    }
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { Stop-Build "Could not create $venv." }
}
& $venvPython -m pip install --disable-pip-version-check --upgrade --force-reinstall --no-deps . -c constraints.txt
if ($LASTEXITCODE -ne 0) { Stop-Build "pip could not install Ycrystal." }
& $venvPython -m pip install --disable-pip-version-check . -c constraints.txt -r packaging\windows\requirements.txt
if ($LASTEXITCODE -ne 0) { Stop-Build "pip could not install the dependencies or the build tools." }
$version = "$(& $venvPython -c "import ycrystal; print(ycrystal.__version__)")".Trim()
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)') { Stop-Build "Unexpected version '$version'." }
$numeric = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
Write-Host "Ycrystal $version"

# ----- 2. Icon -------------------------------------------------------------------------------
Write-Step "Icon $icon"
& $venvPython -c "import sys; from pathlib import Path; from ycrystal.desktop import write_windows_icon; write_windows_icon(Path(sys.argv[1]))" $icon
if ($LASTEXITCODE -ne 0) { Stop-Build "Could not draw the icon." }

# ----- 3. PyInstaller ------------------------------------------------------------------------
Write-Step "PyInstaller: $bundle"
& $venvPython -m PyInstaller --noconfirm --clean --distpath $dist --workpath (Join-Path $build "pyinstaller") packaging\windows\ycrystal.spec
if ($LASTEXITCODE -ne 0) { Stop-Build "PyInstaller failed; see its messages above." }

# ----- 4. Check ------------------------------------------------------------------------------
Write-Step "Check"
$reported = "$(& (Join-Path $bundle "ycrystal-cli.exe") --version)".Trim()
if ($reported -ne "ycrystal $version") { Stop-Build "ycrystal-cli.exe --version reported '$reported'." }
Write-Host $reported
$size = (Get-ChildItem -Recurse -File $bundle | Measure-Object -Sum Length).Sum
Write-Host ("Folder size: {0:N0} MB" -f ($size / 1MB))

# ----- 5. Inno Setup -------------------------------------------------------------------------
if ($NoInstaller) {
    Write-Host ""
    Write-Host "Done (no installer): $bundle"
    exit 0
}
Write-Step "Inno Setup"
$iscc = Find-InnoCompiler
if (-not $iscc) {
    Stop-Build ("Inno Setup 6 was not found. Install it with " +
        "'winget install --id JRSoftware.InnoSetup --exact', or build with -NoInstaller.")
}
& $iscc "/DAppVersion=$version" "/DAppVersionNumeric=$numeric" "/DBundleDir=$bundle" "/DIconFile=$icon" "/DOutputDir=$dist" packaging\windows\ycrystal.iss
if ($LASTEXITCODE -ne 0) { Stop-Build "Inno Setup failed; see its messages above." }
$setup = Join-Path $dist "Ycrystal-$version-windows-x64-setup.exe"
if (-not (Test-Path $setup)) { Stop-Build "The installer $setup is missing." }
Write-Host ""
Write-Host ("Installer: {0} ({1:N0} MB)" -f $setup, ((Get-Item $setup).Length / 1MB)) -ForegroundColor Green
exit 0
