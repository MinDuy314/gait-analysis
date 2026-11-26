# Gait Analysis Backend Startup Script
$projectDir = "C:\Users\nduym\Documents\Gait-analysis"
$env:PYTHONPATH = $projectDir
Set-Location $projectDir
Write-Host "Starting Gait Analysis Backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
& "C:\Users\nduym\miniforge3\envs\yolo\python.exe" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
