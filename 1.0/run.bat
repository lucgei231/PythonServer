:start
@echo off
pip install -r requirements.txt
cd /d D:\Desktop\pserver\1.0\
python app.py
echo There has been an error. Restarting now...
goto start
