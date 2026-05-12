@echo off
setlocal

echo ==========================================
echo PAINEL PCP - BR SUPPLY
echo Atualizando app.py e iniciando o sistema
echo ==========================================

set "APP_DIR=C:\Users\william.mattje.BRSUPPLY\OneDrive - BR SUPPLY\PainelPCP"
set "DOWNLOADS=%USERPROFILE%\Downloads"

echo.
echo [1/5] Verificando pasta do sistema...
if not exist "%APP_DIR%" (
    echo ERRO: Pasta %APP_DIR% nao encontrada.
    pause
    exit /b 1
)

echo.
echo [2/5] Localizando app.py mais recente em Downloads...

set "NOVOAPP="
for /f "delims=" %%F in ('dir /b /a-d /o-d "%DOWNLOADS%\app*.py" 2^>nul') do (
    set "NOVOAPP=%DOWNLOADS%\%%F"
    goto :achou
)

:achou
if "%NOVOAPP%"=="" (
    echo ERRO: Nenhum arquivo app*.py encontrado em %DOWNLOADS%.
    echo Baixe primeiro o app.py corrigido.
    pause
    exit /b 1
)

echo Arquivo encontrado:
echo %NOVOAPP%

echo.
echo [3/5] Copiando app.py para %APP_DIR%...
copy /Y "%NOVOAPP%" "%APP_DIR%\app.py"

if errorlevel 1 (
    echo ERRO ao copiar o app.py.
    pause
    exit /b 1
)

echo.
echo [4/5] Verificando ambiente virtual...

cd /d "%APP_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Criando...
    python -m venv .venv

    echo Instalando dependencias...
    .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
    .\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
)

echo.
echo [5/5] Iniciando painel...
echo Acesse no navegador:
echo http://localhost:8501
echo.

.\.venv\Scripts\python.exe -m streamlit run app.py

pause