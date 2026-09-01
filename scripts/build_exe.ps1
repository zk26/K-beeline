# K-Beeline exe 构建脚本（PyInstaller）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$PyInstaller = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $PyInstaller)) {
    throw "未找到 .venv 中的 pyinstaller，请先执行: .venv\Scripts\python -m pip install -r requirements.txt"
}

Write-Host "==> 清理旧构建产物..."
& $PyInstaller --noconfirm --clean `
    --name KBeeline `
    --windowed --onedir `
    --icon "assets\icons\app.ico" `
    --add-data "assets;assets" `
    --collect-data selenium `
    --hidden-import selenium.webdriver.edge.webdriver `
    --hidden-import selenium.webdriver.edge.service `
    --hidden-import selenium.webdriver.edge.options `
    --hidden-import selenium.webdriver.chrome.webdriver `
    --hidden-import selenium.webdriver.chrome.service `
    --hidden-import selenium.webdriver.chrome.options `
    --hidden-import selenium.webdriver.firefox.webdriver `
    --hidden-import selenium.webdriver.firefox.service `
    --hidden-import selenium.webdriver.firefox.options `
    --hidden-import selenium.webdriver.common.service `
    --paths "$ProjectRoot" `
    "run.py"

if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败 (exit=$LASTEXITCODE)" }
Write-Host "==> 构建完成: $ProjectRoot\dist\KBeeline\KBeeline.exe"
