@echo off
chcp 65001 > nul
REM ==========================================================
REM  Gera o executavel do Sistema da Oficina (Windows)
REM  Resultado: dist\SistemaOficina\SistemaOficina.exe
REM
REM  Rode no SEU computador. O notebook da loja nao precisa de
REM  Python: basta copiar para ele a pasta dist\SistemaOficina.
REM ==========================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado.
    echo Instale pelo site python.org marcando "Add python.exe to PATH".
    goto erro
)

REM Aviso para o Python da Microsoft Store (caminhos longos demais para o PySide6)
python -c "import sys; sys.exit(1 if 'WindowsApps' in sys.executable or 'PythonSoftwareFoundation' in sys.prefix else 0)"
if errorlevel 1 (
    echo.
    echo ATENCAO: este Python foi instalado pela Microsoft Store.
    echo Ele costuma dar erro de "Long Path" ao instalar o PySide6.
    echo Se der erro, desinstale-o e instale o Python do site python.org.
    echo.
)

REM Ambiente virtual dentro da pasta do projeto: caminho curto e isolado
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Criando ambiente virtual .venv...
    python -m venv .venv || goto erro
)
set PY=.venv\Scripts\python.exe

echo [2/4] Instalando dependencias...
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -r requirements-dev.txt || goto erro

echo [3/4] Rodando os testes...
"%PY%" -m pytest -q || goto erro

echo [4/4] Gerando o executavel...
"%PY%" -m PyInstaller --noconfirm --clean --windowed --name SistemaOficina ^
    --icon "oficina\ui\recursos\icone.ico" ^
    --add-data "oficina\ui\recursos;oficina\ui\recursos" ^
    main.py || goto erro

echo.
echo Pronto! Copie a pasta dist\SistemaOficina inteira para o notebook da loja
echo e crie um atalho na area de trabalho para SistemaOficina.exe
echo (os dados ficam em Documentos\Sistema Oficina e nao sao afetados).
pause
exit /b 0

:erro
echo.
echo Ocorreu um erro. Veja as mensagens acima.
echo Se aparecer "Long Path": instale o Python do site python.org e, no fim
echo da instalacao, clique em "Disable path length limit".
pause
exit /b 1
