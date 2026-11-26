# Gait Analysis Backend Startup Script
$projectDir = "C:\Users\nduym\Documents\Gait-analysis"
$env:PYTHONPATH = $projectDir
Set-Location $projectDir
Write-Host "Starting Gait Analysis Backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
if (Get-Command tailscale -ErrorAction SilentlyContinue) {
    Write-Host "Ensuring Tailscale Funnel is active for port 8000..." -ForegroundColor Green
    tailscale funnel --bg 8000 | Out-Null
}
& "C:\Users\nduym\miniforge3\envs\yolo\python.exe" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
