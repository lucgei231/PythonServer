@echo off
REM This script is used to run the WSL terminal app
:start
pip install -r .\requirements.txt
C:\Users\adam\AppData\Local\Programs\Python\Python312\python.exe .\wsl-terminal-app.py
goto start