# OptiLag — gerar executavel Windows (PyInstaller)
# Uso (PowerShell, na pasta do projeto):
#   pip install pyinstaller
#   .\build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> A instalar PyInstaller..."
python -m pip install -q pyinstaller

$icons = "icons"
$addData = @()
if (Test-Path $icons) {
  # Windows PyInstaller: origem;destino
  $addData += "--add-data", "$icons;icons"
}
if (Test-Path "conf\wg-optilag.conf.example") {
  $addData += "--add-data", "conf;conf"
}

$args = @(
  "--noconfirm",
  "--clean",
  "--windowed",
  "--name", "OptiLag",
  "--paths", "."
) + $addData + @(
  "--hidden-import", "customtkinter",
  "--hidden-import", "PIL",
  "--hidden-import", "PIL._tkinter_finder",
  "--collect-all", "customtkinter",
  "optilag_pubg.py"
)

Write-Host "==> A compilar (pode demorar varios minutos)..."
python -m PyInstaller @args

Write-Host ""
Write-Host "OK. Executavel em: dist\OptiLag\OptiLag.exe  (onedir)"
Write-Host "Ou, se usares --onefile no futuro: dist\OptiLag.exe"
Write-Host "Copia a pasta dist\OptiLag para outro PC para testar."
