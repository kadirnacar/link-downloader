rem ytdlp-studio:build-all-bat v1
@echo off
rem build-all-windows.ps1 dosyasini PowerShell ile calistirir
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-all-windows.ps1" %*
