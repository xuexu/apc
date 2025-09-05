@echo off
REM Build a new Animal Population Changer - Revived for Windows
rmdir /s /q "%CD%\build" 2>nul
rmdir /s /q "%CD%\dist\apcgui" 2>nul
pyinstaller apcgui.spec