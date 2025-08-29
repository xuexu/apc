@echo off
REM Build a new Animal Population Changer - Revived for Windows
rmdir /s /q build 2>nul
rmdir /s /q dist\apcgui 2>nul
pyinstaller apcgui.spec