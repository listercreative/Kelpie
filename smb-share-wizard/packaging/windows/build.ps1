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

python -m pip install --upgrade pip
python -m pip install pyinstaller rich

pyinstaller `
  --onefile `
  --windowed `
  --name Kelpie `
  --hidden-import=core --hidden-import=cli --hidden-import=gui --hidden-import=tui `
  --collect-all=rich `
  --distpath . `
  --workpath build `
  --specpath build `
  ..\..\src\main.py

wix build kelpie.wxs -ext WixToolset.UI.wixext -out Kelpie.msi

Write-Host "Built Kelpie.msi"
