@echo off
title ArenaPlay Capture Supervisor

cd /d D:\PROJETOS\Meu lance\arenaplay

echo ================================
echo ArenaPlay Capture iniciando...
echo ================================

:loop
echo [%date% %time%] Iniciando capturador...

python arenaplay_capture.py >> log.txt 2>&1

echo.
echo [%date% %time%] O capturador parou ou deu erro.
echo Reiniciando em 5 segundos...

timeout /t 5

goto loop