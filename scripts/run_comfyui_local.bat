@echo off
rem 로컬 전용(127.0.0.1) + ComfyUI-Manager 활성화
cd /d %~dp0
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 127.0.0.1 --port 8188 --enable-manager
pause
