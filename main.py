"""
Instituto Amostral — MVP Backend
FastAPI server para geração de planos amostrais.
"""

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json

from amostragem import gerar_plano, listar_municipios, listar_ufs, calcular_amostra_municipio

# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="Instituto Amostral — MVP",
    description="API para geração de planos amostrais eleitorais",
    version="1.0.0",
)

# CORS para frontend local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve arquivos estáticos (frontend)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """Redireciona para o frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/ufs", summary="Lista UFs disponíveis")
def get_ufs():
    """Retorna lista de UFs com dados disponíveis."""
    try:
        ufs = listar_ufs()
        return {"ufs": ufs}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/municipios", summary="Lista municípios por UF")
def get_municipios(uf: str = Query(None, description="Sigla do estado (ex: SP, RJ, TO). Opcional")):
    """Retorna lista de municípios, opcionalmente filtrada por UF."""
    try:
        municipios = listar_municipios(uf)
        # Retorna objetos com chave MUNICIPIO (compatível com app.js)
        return JSONResponse(
            content={"municipios": municipios},
            media_type="application/json; charset=utf-8",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/calcular-amostra", summary="Calcula amostra recomendada")
def get_calcular_amostra(
    uf: str = Query(..., description="Sigla do estado (ex: TO, SP)"),
    municipio: str = Query(..., description="Nome do município"),
    confianca: float = Query(0.95, description="Nível de confiança (0.90, 0.95, 0.99)"),
    margem_erro: float = Query(0.05, description="Margem de erro (ex: 0.05 = 5%)"),
):
    """
    Calcula o tamanho de amostra estatisticamente recomendado para o município,
    com base nos dados reais do TSE (eleitorado por zona) e IBGE (IDH, população).

    Retorna:
    - Valor recomendado (pronto para usar)
    - Mínimo pela fórmula de Cochran
    - Mínimo por cobertura de zonas
    - 7 cenários alternativos (confiança × margem de erro)
    - Justificativa estatística completa
    """
    try:
        resultado = calcular_amostra_municipio(
            uf=uf,
            municipio=municipio,
            confianca=confianca,
            margem_erro=margem_erro,
        )
        return resultado
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.get("/plano", summary="Gera plano amostral")
def get_plano(
    uf: str = Query(..., description="Sigla do estado (ex: TO, SP)"),
    municipio: str = Query(..., description="Nome do município"),
    amostra: int = Query(None, ge=100, le=10000, description="Tamanho desejado da amostra (omitir = calcular automaticamente)"),
    formato: str = Query("pdf", pattern="^(pdf|markdown|md|excel)$", description="Formato de saída"),
    confianca: float = Query(0.95, description="Nível de confiança (0.90, 0.95, 0.99)"),
    margem_erro: float = Query(0.05, description="Margem de erro (ex: 0.05 = 5%)"),
):
    """
    Gera plano amostral completo para o município informado.
    
    Retorna metadados e caminhos dos arquivos gerados.
    """
    try:
        resultado = gerar_plano(
            uf=uf,
            municipio=municipio,
            amostra=amostra,
            formato=formato,
            confianca=confianca,
            margem_erro=margem_erro,
        )
        
        # Converte caminhos para URLs de download
        resposta = {
            "meta": resultado["meta"],
            "arquivos": {},
            "zonas": resultado.get("zonas", []),
            "benchmark": resultado.get("benchmark", {}),
        }
        
        if "excel" in resultado:
            nome = os.path.basename(resultado["excel"])
            resposta["arquivos"]["excel"] = f"/download/excel/{nome}"
        
        if "pdf" in resultado:
            nome = os.path.basename(resultado["pdf"])
            resposta["arquivos"]["pdf"] = f"/download/pdf/{nome}"
        
        if "markdown" in resultado:
            nome = os.path.basename(resultado["markdown"])
            resposta["arquivos"]["markdown"] = f"/download/markdown/{nome}"
        
        return resposta
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@app.get("/download/excel/{filename}", summary="Download Excel")
def download_excel(filename: str):
    """Download do arquivo Excel gerado."""
    caminho = os.path.join(BASE_DIR, "outputs", filename)
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(
        caminho,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.get("/download/pdf/{filename}", summary="Download PDF")
def download_pdf(filename: str):
    """Download do arquivo PDF gerado."""
    caminho = os.path.join(BASE_DIR, "outputs", filename)
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(caminho, media_type="application/pdf", filename=filename)


@app.get("/download/markdown/{filename}", summary="Download Markdown")
def download_markdown(filename: str):
    """Download do arquivo Markdown gerado."""
    caminho = os.path.join(BASE_DIR, "outputs", filename)
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(caminho, media_type="text/markdown", filename=filename)


@app.get("/health", summary="Health check")
def health():
    """Verifica se o serviço está funcionando."""
    return {"status": "ok", "service": "Instituto Amostral MVP"}
