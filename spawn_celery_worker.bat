@echo off
setlocal enabledelayedexpansion

:: Set the command to run (change this to your desired command)
set "COMMAND=make celery"

:: Set the number of processes to spawn
set "NUM_PROCESSES=20"

echo Spawning %NUM_PROCESSES% processes...

for /L %%i in (1,1,%NUM_PROCESSES%) do (
    start "Process %%i" cmd /c %COMMAND%
)

echo All processes started!
exit /b
