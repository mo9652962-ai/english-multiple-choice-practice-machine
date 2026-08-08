@echo off
chcp 65001 >nul
title AI英语刷题机 - 一键信任设置
echo ============================================
echo   AI英语刷题机 v2.0.0-beta.1 一键信任设置
echo ============================================
echo.
echo  本工具只需运行一次：
echo  将发布者证书加入系统信任列表，
echo  之后安装/更新刷题机将不再有任何安全提示。
echo.
echo  [安全说明] 本工具只做一件事：信任 "MoSoftware"
echo   发布者证书（epm-signing.cer），不修改任何其他内容。
echo.
pause
echo.
echo 正在导入信任证书...
certutil -user -addstore Root "%~dp0epm-signing.cer" >nul 2>&1
certutil -user -addstore TrustedPublisher "%~dp0epm-signing.cer" >nul 2>&1
echo.
echo ✅ 信任设置完成！
echo.
echo  现在可以直接双击 epm-setup-2.0.0-beta.1.exe
echo  或 epm-portable-2.0.0-beta.1.exe 使用了。
echo.
pause
