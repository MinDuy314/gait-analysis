@echo off
title Gait Analysis Backend Server
cd /d "C:\Users\nduym\Documents\Gait-analysis"
set "PYTHONPATH=C:\Users\nduym\Documents\Gait-analysis"
echo Starting Gait Analysis Backend on http://127.0.0.1:8000 ...
"C:\Users\nduym\miniforge3\envs\yolo\python.exe" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
pause
