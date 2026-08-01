# 打包后端侧车（先排除 OCR 以缩小体积），产物复制到 Tauri 侧车目录。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到 $Python，请先执行 py -3.11 -m venv .venv 并安装依赖"
}

& $Python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    throw "安装 PyInstaller 失败"
}

& $Python -m PyInstaller `
    --onefile `
    --name tender-backend `
    --clean `
    --noconfirm `
    --add-data "app/skills/prompts;app/skills/prompts" `
    --exclude-module paddleocr `
    --exclude-module paddlepaddle `
    --exclude-module matplotlib `
    --exclude-module scipy `
    --exclude-module sklearn `
    --hidden-import aioboto3.s3 `
    --collect-submodules aioboto3 `
    sidecar_entry.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败"
}

$TargetDir = Join-Path $Root "..\desktop\src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
$Target = Join-Path $TargetDir "tender-backend-x86_64-pc-windows-msvc.exe"
Copy-Item -Force (Join-Path $Root "dist\tender-backend.exe") $Target

Write-Host ""
Write-Host "侧车已生成：$Target"
Write-Host "接下来执行：cd desktop; npm run tauri:build"
