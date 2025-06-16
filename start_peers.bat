@echo off
title Peer Launcher

:: Habilita a expansao de variaveis dentro de loops.
setlocal enabledelayedexpansion

:: Configuracoes
set PEER_COUNT=8
set BASE_PORT=5001

echo Iniciando %PEER_COUNT% peers em novas janelas...
echo.

:: Loop para iniciar cada peer.
FOR /L %%i IN (1, 1, %PEER_COUNT%) DO (
    set /A PORT=!BASE_PORT! + %%i - 1
    echo Iniciando peer_%%i na porta !PORT!
    
    :: O comando 'start' abre uma nova janela do Prompt de Comando.
    :: O titulo da janela e definido como "Peer %%i".
    :: 'cmd /k' mantem a janela aberta apos o script python finalizar, permitindo ver a saida.
    start "Peer %%i" cmd /k python peer.py peer_%%i !PORT!
)

echo.
echo Todos os peers foram iniciados em janelas separadas.