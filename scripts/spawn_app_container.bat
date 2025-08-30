@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM Base port for the first container
SET BASE_PORT=8088

REM Number of containers
SET NUM_CONTAINERS=5

REM Image name
SET IMAGE_NAME=notifyr:fastapi

REM Build the local Docker image first
docker build -t %IMAGE_NAME% .

FOR /L %%i IN (0,1,%NUM_CONTAINERS%-1) DO (
    SET /A PORT=%BASE_PORT% + %%i
    SET CONTAINER_NAME=ntfyr-app-!PORT!

    echo Starting container !CONTAINER_NAME! on port !PORT!...

    docker run -d ^
        --name !CONTAINER_NAME! ^
        -p !PORT!:8088 ^
        -v "%cd%\rate_limits.json:/run/secrets/rate_limits:ro" ^
        --env-file .env ^
        -e MODE=prod ^
        --label "com.docker.compose.service=app" ^
        --link redis ^
        --link mongodb ^
        %IMAGE_NAME% ^
        python main.py -H 0.0.0.0 -p 8088 -t solo
)

echo All containers started.
ENDLOCAL
pause
