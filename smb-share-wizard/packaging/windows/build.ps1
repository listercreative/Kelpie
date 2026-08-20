# Build Kelpie.msi on a real Windows machine.
# Run from this directory (packaging\windows) in PowerShell.
#
# Prerequisites:
#   - Python 3.8+ on PATH
#   - .NET SDK (for the WiX v5 CLI): https://dotnet.microsoft.com/download
#
# One-time tool setup:
#   dotnet tool install --global wix --version 5.0.2
#   wix extension add WixToolset.UI.wixext/5.0.2

$ErrorActionPreference = "Stop"

# $ErrorActionPreference only catches PowerShell-native errors, not a
# non-zero exit code from an external .exe - check that explicitly after
# each native tool invocation so a failed step can't silently fall through
# to "Built Kelpie.msi".
function Assert-LastExitCode($what) {
    if ($LASTEXITCODE -ne 0) {
        throw "$what failed (exit code $LASTEXITCODE)"
    }
}

# Resolve everything from the script's own folder, not the caller's working
# directory: PyInstaller resolves --add-data's relative source path against
# its --specpath (build\), not the invocation directory, so a plain
# "..\..\src\..." here lands one level short. Absolute paths sidestep that
# entirely, and also let this script work no matter where it's invoked from.
$RepoSrc = Resolve-Path (Join-Path $PSScriptRoot "..\..\src")

python -m pip install --upgrade pip
python -m pip install pyinstaller rich

pyinstaller `
  --onefile `
  --windowed `
  --name Kelpie `
  --icon (Join-Path $PSScriptRoot "kelpie_icon.ico") `
  --add-data "$(Join-Path $RepoSrc 'kelpie_icon.png');." `
  --hidden-import=core --hidden-import=cli --hidden-import=gui --hidden-import=tui `
  --collect-all=rich `
  --distpath $PSScriptRoot `
  --workpath (Join-Path $PSScriptRoot "build") `
  --specpath (Join-Path $PSScriptRoot "build") `
  (Join-Path $RepoSrc "main.py")
Assert-LastExitCode "pyinstaller"

wix build (Join-Path $PSScriptRoot "kelpie.wxs") -ext WixToolset.UI.wixext -out (Join-Path $PSScriptRoot "Kelpie.msi")
Assert-LastExitCode "wix build"

Write-Host "Built Kelpie.msi"
