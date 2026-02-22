@echo off
REM Script de bootstrap local do MVP.
REM Objetivo: preparar ambiente, garantir dados e subir a API.
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║        INSTITUTO AMOSTRAL — MVP v1.0                ║
echo  ║        Sistema de Planos Amostrais Eleitorais        ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Etapa 1: instala dependências Python listadas em requirements.
echo [1/3] Verificando dependencias Python...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

REM Etapa 2: gera base local apenas se ainda não existir.
REM Isso evita downloads desnecessários em toda execução.
echo [2/3] Gerando dados de amostra (TSE + IBGE)...
if not exist "dados\tse.csv" (
    python gerar_dados.py
) else (
    echo      Dados ja existem. Pulando geracao.
)

REM Etapa 3: sobe servidor FastAPI em modo de desenvolvimento.
echo [3/3] Iniciando servidor FastAPI...
echo.
echo  Acesse: http://127.0.0.1:8000
echo  Docs:   http://127.0.0.1:8000/docs
echo.
echo  Pressione Ctrl+C para parar o servidor.
echo.

uvicorn main:app --reload --host 127.0.0.1 --port 8000
