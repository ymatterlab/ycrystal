<#
.SYNOPSIS
Install Ycrystal on Windows from this checkout, with what it needs.

.DESCRIPTION
Run it in PowerShell, in the checkout (the folder that "git clone" made):

    powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1

It installs what is missing, so it can be run again at any time; after "git pull" it
updates the installation. In order:

1. Python 3.12, with winget for the current user, unless "py -3.12" finds one;
2. the virtual environment .venv in the checkout, and Ycrystal into it, with the
   tested versions of constraints.txt (about 300 MB of packages the first time);
3. POV-Ray for Windows 3.7, with winget (its official installer from povray.org;
   Windows asks for permission), unless it is installed;
4. if POV-Ray for Windows would ask at every start whether to download its editor:
   POV-Ray opens once, so that the question can be answered for good;
5. the Start-menu entry "Ycrystal" and the file type of .ycrystal projects
   (ycrystal.exe --install-desktop);
6. the renderer check (ycrystal.exe --check-renderer).

Only the POV-Ray installer needs administrator rights. The exit status is 0 when
everything is ready, and 1 when a step failed or rendering is not ready yet.

.PARAMETER Python
A Python interpreter (3.10 or newer; 3.12 is tested) to create .venv with, instead of
"py -3.12". Ignored when .venv exists.

.PARAMETER Dev
Also install the developer tools (pytest, ruff, pre-commit): pip's ".[dev]".

.PARAMETER NoPovray
Do not install POV-Ray for Windows. Viewing structures and exporting scenes work
without it; previews and images need it.

.PARAMETER NoStartMenu
Do not add the Start-menu entry and the project file type.
#>
[CmdletBinding()]
param(
    [string]$Python,
    [switch]$Dev,
    [switch]$NoPovray,
    [switch]$NoStartMenu
)

# Native programs report through their exit status, checked after each one. Windows
# PowerShell 5.1 turns their error output into exceptions under "Stop", so not here.
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$ycrystal = Join-Path $venv "Scripts\ycrystal.exe"
$problems = New-Object System.Collections.Generic.List[string]

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Stop-Install([string]$Text) {
    Write-Host ""
    Write-Host "ERROR: $Text" -ForegroundColor Red
    exit 1
}

function Update-SessionPath {
    # winget adds programs to the PATH of new terminals; add them to this one too.
    $known = $env:Path -split ";"
    foreach ($scope in "Machine", "User") {
        $value = [Environment]::GetEnvironmentVariable("Path", $scope)
        if (-not $value) { continue }
        foreach ($entry in $value -split ";") {
            if ($entry -and ($known -notcontains $entry)) {
                $env:Path = "$env:Path;$entry"
                $known += $entry
            }
        }
    }
}

function Test-Winget {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

function Install-Package([string]$Id, [string[]]$Options) {
    # winget's exit status is not 0 when the package is already there, so the caller
    # looks for the program again instead.
    & winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements @Options
    Update-SessionPath
}

function Find-Python312 {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) { return $null }
    $found = & $launcher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $found) { return $null }
    return "$found".Trim()
}

function Find-Povray {
    $code = @'
import ycrystal.render.povray as p
try:
    print(p.find_povray())
except p.PovrayNotFoundError:
    print('')
'@
    $found = & $venvPython -c $code
    return "$found".Trim()
}

function Test-EditorQuestion([string]$Engine) {
    $code = @'
import sys
import ycrystal.render.povray as p
print(int(p.windows_engine_conflict(sys.argv[1]) == p.EDITOR_QUESTION_MESSAGE))
'@
    $answer = & $venvPython -c $code $Engine
    return "$answer".Trim() -eq "1"
}

Write-Host "Installing Ycrystal from $root"
if (-not (Test-Path (Join-Path $root "pyproject.toml"))) {
    Stop-Install "This script belongs in the scripts folder of a Ycrystal checkout."
}

# ----- 1. Python and the virtual environment -------------------------------------------
Write-Step "Python and the virtual environment .venv"
if (Test-Path $venvPython) {
    Write-Host "Using the existing environment $venv"
} else {
    $base = $Python
    if (-not $base) {
        $base = Find-Python312
        if (-not $base) {
            if (-not (Test-Winget)) {
                Stop-Install ("Python 3.12 was not found, and winget is not available to install it. " +
                    "Install Python 3.12 from https://www.python.org/downloads/windows/ and run this script again.")
            }
            Write-Host "Python 3.12 was not found; installing it with winget, for the current user."
            Install-Package "Python.Python.3.12" @("--scope", "user")
            $base = Find-Python312
            if (-not $base) {
                Stop-Install "Python 3.12 is still not found. Open a new PowerShell window and run this script again."
            }
        }
    }
    if ($base -like "*\WindowsApps\*") {
        Stop-Install "$base is the Microsoft Store alias, not a Python installation. Use Python 3.12 from python.org or winget."
    }
    $version = & $base -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ($LASTEXITCODE -ne 0 -or -not $version) { Stop-Install "$base does not run." }
    $version = "$version".Trim()
    if ([version]$version -lt [version]"3.10") {
        Stop-Install "$base is Python $version; Ycrystal needs Python 3.10 or newer (3.12 is tested)."
    }
    Write-Host "Creating $venv with Python $version ($base)"
    & $base -m venv $venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { Stop-Install "Could not create $venv." }
}

# ----- 2. Ycrystal -------------------------------------------------------------------------
Write-Step "Ycrystal and its packages (about 300 MB the first time)"
$requirement = "."
if ($Dev) { $requirement = ".[dev]" }
Push-Location $root
try {
    & $venvPython -m pip install --disable-pip-version-check -e $requirement -c constraints.txt
    $pipStatus = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($pipStatus -ne 0) {
    Stop-Install ("pip could not install Ycrystal; see its messages above. If .venv is broken, " +
        "delete the folder .venv and run this script again.")
}
& $ycrystal --version

# ----- 3. POV-Ray for Windows ------------------------------------------------------------
Write-Step "POV-Ray for Windows 3.7"
$engine = Find-Povray
if (-not $engine -and -not $NoPovray) {
    if (Test-Winget) {
        Write-Host "Installing POV-Ray for Windows 3.7 with winget (its official installer; Windows asks for permission)."
        Install-Package "PersistenceOfVisionRaytracer.POVRay" @()
        $engine = Find-Povray
    } else {
        Write-Host "winget is not available to install POV-Ray for Windows."
    }
}
if ($engine) {
    Write-Host "Found $engine"
} else {
    $problems.Add("POV-Ray for Windows 3.7 is not installed: install it from https://www.povray.org/download/ " +
        "and run this script again. Viewing and exporting scenes work without it.")
}

# ----- 4. POV-Ray's question about its editor ----------------------------------------------
if ($engine -and (Test-EditorQuestion $engine)) {
    Write-Step "POV-Ray for Windows asks about its editor"
    Write-Host "Without its editor (a separate download), POV-Ray for Windows asks at every start"
    Write-Host "whether to download it, and Ycrystal's renders would wait for that answer."
    Write-Host "POV-Ray opens now, once. In its window:"
    Write-Host "  1. answer No to 'Could not load internal editor - download it?';"
    Write-Host "  2. untick Options > Other Settings > Use Editor;"
    Write-Host "  3. close POV-Ray for Windows. The installation then continues."
    Write-Host "(Or answer Yes and install the editor from the page that opens; then run this script again.)"
    Read-Host "Press Enter to open POV-Ray for Windows" | Out-Null
    Start-Process -FilePath $engine -Wait
    if (Test-EditorQuestion $engine) {
        $problems.Add("POV-Ray for Windows still asks about its editor at every start: open it from the Start menu, " +
            "answer No, untick Options > Other Settings > Use Editor, close it, and run this script again.")
    }
}

# ----- 5. Start menu ---------------------------------------------------------------------
if (-not $NoStartMenu) {
    Write-Step "Start menu and .ycrystal projects"
    & $ycrystal --install-desktop
    if ($LASTEXITCODE -ne 0) { $problems.Add("The Start-menu entry could not be added; see the message above.") }
}

# ----- 6. Renderer check -----------------------------------------------------------------
if ($engine -and $problems.Count -eq 0) {
    Write-Step "Renderer check"
    & $ycrystal --check-renderer
    if ($LASTEXITCODE -ne 0) { $problems.Add("The renderer check failed; see its message above.") }
}

Write-Step "Summary"
if (-not $NoStartMenu) {
    Write-Host "Start Ycrystal from the Start menu (Ycrystal), or in PowerShell with:"
} else {
    Write-Host "Start Ycrystal in PowerShell with:"
}
Write-Host "    $ycrystal"
Write-Host "To update later: git pull, then run this script again."
if ($problems.Count -gt 0) {
    Write-Host ""
    Write-Host "Not ready yet:" -ForegroundColor Yellow
    foreach ($problem in $problems) { Write-Host "  - $problem" -ForegroundColor Yellow }
    exit 1
}
Write-Host "Ycrystal is ready." -ForegroundColor Green
exit 0
