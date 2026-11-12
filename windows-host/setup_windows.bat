@echo off
title PulseLink Cast - Windows Setup & Access Configurator
echo ===============================================================
echo   PulseLink Cast Studio - Windows Setup & Firewall Access
echo ===============================================================
echo.
echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
echo.
echo [2/3] Configuring Windows Defender Firewall rules (TCP 5959 / UDP 5960)...
netsh advfirewall firewall add rule name="PulseLink Cast - LAN Screen Stream (TCP 5959)" dir=in action=allow protocol=TCP localport=5959 profile=private,public
netsh advfirewall firewall add rule name="PulseLink Cast - LAN Auto Discovery (UDP 5960)" dir=in action=allow protocol=UDP localport=5960 profile=private,public
echo.
echo [3/3] Building Standalone Windows Executable (PulseLinkCastHost.exe)...
pyinstaller --noconfirm --onefile --windowed --name PulseLinkCastHost --icon=assets/app_icon.ico --add-data "assets;assets" main.py
echo.
echo Build complete! Executable saved to dist\PulseLinkCastHost.exe
pause
