@echo off
REM =============================================================
REM 墨题 (English Practice Machine) — Windows 部署脚本
REM 用途: 培训机构/机构买家在 Windows 服务器或本机私有化部署
REM 用法: 双击运行 或 命令行执行 deploy_windows.bat
REM =============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0\.."

echo [deploy] ============================================
echo [deploy]  墨题部署开始  (Windows)
echo [deploy] ============================================

REM ---------- 1. 检查 Python ----------
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3.12"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo [deploy-error] 未找到 Python 3.12, 请先安装: https://www.python.org/downloads/
        exit /b 1
    )
)

REM ---------- 2. 创建 venv + 装依赖 ----------
if not exist ".venv" (
    echo [deploy] 创建虚拟环境...
    %PY% -m venv .venv
)
echo [deploy] 安装后端依赖...
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [deploy-error] 依赖安装失败, 请检查网络/镜像
    exit /b 1
)

REM ---------- 3. 前端构建 ----------
if exist "frontend\package.json" (
    echo [deploy] 构建前端...
    pushd frontend
    where npm >nul 2>nul
    if errorlevel 1 (
        echo [deploy-error] 未找到 Node.js/npm, 请安装 Node 18+: https://nodejs.org/
        popd
        exit /b 1
    )
    call npm install --silent
    call npm run build
    if errorlevel 1 (
        echo [deploy-error] 前端构建失败
        popd
        exit /b 1
    )
    popd
)

REM ---------- 4. 数据目录 ----------
if not exist "backend\data\uploads" mkdir "backend\data\uploads"
if not exist "backend\data\question_banks" mkdir "backend\data\question_banks"

REM ---------- 5. 完成 ----------
echo [deploy] ============================================
echo [deploy]  部署完成!
echo [deploy]  启动后端:   cd backend ^&^& .venv\..\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8765
echo [deploy]  或双击 start_backend.bat
echo [deploy]  访问:      http://localhost:8765
echo [deploy]  多用户:    如需开启用户隔离, 设环境变量 EPM_AUTH=1
echo [deploy] ============================================
pause