@echo off
cd /d D:\RP_AI_EA

echo Starting market sync...
start powershell -ExecutionPolicy Bypass -File sync_market.ps1

timeout /t 3

echo Starting decision sync...
start powershell -ExecutionPolicy Bypass -File sync_decision.ps1

timeout /t 3

echo Starting AI Engine...
start cmd /k run_ai.bat

echo ALL SYSTEMS STARTED