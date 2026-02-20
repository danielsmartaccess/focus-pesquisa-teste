"""
Gerador de Dados Reais — Instituto Amostral MVP

Baixa dados oficiais públicos e gera os arquivos locais usados pela aplicação:
- dados/ibge.csv: municípios + população residente estimada (IBGE)
- dados/tse.csv: eleitorado agregado por município/zona/gênero (TSE)

Fontes:
- IBGE Localidades API: https://servicodados.ibge.gov.br/api/v1/localidades/municipios
- IBGE Agregados API (variável 9324): população residente estimada
- TSE Dados Abertos (CKAN): dataset "Eleitorado Atual"
"""

from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import time
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(BASE_DIR, "dados")
os.makedirs(DADOS_DIR, exist_ok=True)

IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome"
IBGE_POP_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-6/variaveis/9324?localidades=N6[all]"
TSE_CKAN_SEARCH_URL = "https://dadosabertos.tse.jus.br/api/3/action/package_search?q=Eleitorado%20Atual"


def normalizar_nome(texto: str) -> str:
    """Normaliza nome para comparação robusta entre fontes."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper().strip()
    s = " ".join(s.split())
    return s


def buscar_municipios_ibge() -> pd.DataFrame:
    """Retorna DataFrame com UF, MUNICIPIO e ID_IBGE (dados oficiais IBGE)."""
    print("🌐 IBGE: baixando lista oficial de municípios...")
    resp = requests.get(IBGE_MUNICIPIOS_URL, timeout=90)
    resp.raise_for_status()
    dados = resp.json()

    linhas = []
    for m in dados:
        micro = m.get("microrregiao") or {}
        meso = micro.get("mesorregiao") or {}
        uf = meso.get("UF") or {}

        sigla = uf.get("sigla")
        if not sigla:
            ri = m.get("regiao-imediata") or {}
            rint = ri.get("regiao-intermediaria") or {}
            uf2 = rint.get("UF") or {}
            sigla = uf2.get("sigla")

        if not sigla:
            continue

        linhas.append(
            {
                "UF": sigla,
                "MUNICIPIO": m.get("nome", "").strip(),
                "ID_IBGE": int(m["id"]),
            }
        )

    df = pd.DataFrame(linhas)
    print(f"✅ IBGE: {len(df):,} municípios carregados")
    return df


def buscar_populacao_ibge() -> tuple[dict[int, int], int]:
    """
    Retorna:
      - mapa {ID_IBGE: POPULACAO_TOTAL}
      - ano de referência detectado (último disponível)
    """
    print("🌐 IBGE: baixando população residente estimada...")
    resp = requests.get(IBGE_POP_URL, timeout=120)
    resp.raise_for_status()
    payload = resp.json()

    if not payload or not payload[0].get("resultados"):
        raise RuntimeError("Resposta inesperada da API de população do IBGE.")

    series = payload[0]["resultados"][0]["series"]
    populacao_por_id: dict[int, int] = {}
    anos_detectados: set[int] = set()

    for item in series:
        localidade = item.get("localidade") or {}
        local_id = localidade.get("id")
        if not local_id:
            continue

        serie = item.get("serie") or {}
        if not serie:
            continue

        anos_validos = [int(ano) for ano, valor in serie.items() if str(valor).strip() not in {"", "...", "-"}]
        if not anos_validos:
            continue

        ano_ref = max(anos_validos)
        valor = serie.get(str(ano_ref), "0")
        try:
            pop = int(float(str(valor).replace(",", ".")))
        except ValueError:
            continue

        populacao_por_id[int(local_id)] = pop
        anos_detectados.add(ano_ref)

    ano_global = max(anos_detectados) if anos_detectados else datetime.now().year
    print(f"✅ IBGE: população carregada para {len(populacao_por_id):,} municípios (ref. {ano_global})")
    return populacao_por_id, ano_global


def montar_base_ibge() -> tuple[pd.DataFrame, int]:
    """Gera DataFrame final do IBGE com população real."""
    df_mun = buscar_municipios_ibge()
    pop_map, ano_ref = buscar_populacao_ibge()

    df_mun["POPULACAO_TOTAL"] = df_mun["ID_IBGE"].map(pop_map)
    faltantes = int(df_mun["POPULACAO_TOTAL"].isna().sum())
    if faltantes:
        print(f"⚠️  IBGE: {faltantes} municípios sem população no payload; preenchendo com 0")
        df_mun["POPULACAO_TOTAL"] = df_mun["POPULACAO_TOTAL"].fillna(0)

    df_mun["POPULACAO_TOTAL"] = df_mun["POPULACAO_TOTAL"].astype(int)
    return df_mun, ano_ref


def buscar_recursos_tse_por_uf() -> dict[str, str]:
    """Obtém URLs por UF do dataset oficial 'Eleitorado Atual' do TSE."""
    print("🌐 TSE: consultando catálogo de dados abertos...")
    resp = requests.get(TSE_CKAN_SEARCH_URL, timeout=120)
    resp.raise_for_status()
    payload = resp.json()

    if not payload.get("success"):
        raise RuntimeError("Falha ao consultar catálogo de dados abertos do TSE.")

    resultados = payload.get("result", {}).get("results", [])
    if not resultados:
        raise RuntimeError("Nenhum dataset retornado pelo catálogo do TSE.")

    pkg = next((p for p in resultados if p.get("title") == "Eleitorado Atual"), None)
    if pkg is None:
        pkg = resultados[0]

    recursos = pkg.get("resources", [])
    por_uf: dict[str, str] = {}

    for r in recursos:
        nome = (r.get("name") or "").strip()
        url = r.get("url")
        if not url:
            continue

        if "Perfil do eleitorado por seção eleitoral - Atual" not in nome:
            continue

        prefixo = nome.split(" - ")[0].strip().upper()
        if len(prefixo) == 2 and prefixo.isalpha() and prefixo != "ZZ":
            por_uf[prefixo] = url

    if len(por_uf) < 27:
        print(f"⚠️  TSE: recursos por UF encontrados = {len(por_uf)} (esperado: 27)")
    else:
        print("✅ TSE: recursos de seção eleitoral encontrados para todas as UFs")

    return por_uf


def baixar_arquivo(url: str, destino: str):
    """Baixa arquivo com streaming para evitar estouro de memória."""
    ultima_exc = None
    for tentativa in range(1, 4):
        try:
            with requests.get(url, stream=True, timeout=240) as resp:
                resp.raise_for_status()
                with open(destino, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            return
        except Exception as exc:
            ultima_exc = exc
            if tentativa < 3:
                espera = 2 * tentativa
                print(f"   ⚠️  Falha de download (tentativa {tentativa}/3). Repetindo em {espera}s...")
                time.sleep(espera)

    raise RuntimeError(f"Falha ao baixar arquivo após 3 tentativas: {url}") from ultima_exc


def processar_arquivo_tse_uf(
    uf: str,
    url_zip: str,
    canon_por_uf_norm: dict[tuple[str, str], str],
) -> tuple[list[dict], set[str], list[dict]]:
    """
    Processa 1 UF do TSE e retorna:
      - linhas agregadas por UF, município, zona
    - conjunto de datas de geração detectadas no arquivo
    - linhas de perfil municipal (gênero/instrução/faixa etária)
    """
    print(f"   ↳ {uf}: baixando arquivo oficial...")

    with tempfile.NamedTemporaryFile(suffix=f"_{uf}.zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        baixar_arquivo(url_zip, tmp_path)

        with zipfile.ZipFile(tmp_path) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise RuntimeError(f"Arquivo ZIP de {uf} sem CSV interno.")

            nome_csv = csv_names[0]
            print(f"   ↳ {uf}: processando {nome_csv}...")

            agg_total = defaultdict(int)
            agg_fem = defaultdict(int)
            agg_masc = defaultdict(int)
            secoes_por_zona: defaultdict[tuple[str, str, int], set[int]] = defaultdict(set)
            perfil_municipal: defaultdict[tuple[str, str, str, str], int] = defaultdict(int)
            datas_geracao: set[str] = set()

            usecols = [
                "DT_GERACAO",
                "SG_UF",
                "NM_MUNICIPIO",
                "NR_ZONA",
                "NR_SECAO",
                "DS_GENERO",
                "DS_GRAU_INSTRUCAO",
                "DS_FAIXA_ETARIA",
                "QT_ELEITORES",
            ]

            with zf.open(nome_csv) as f:
                chunks = pd.read_csv(
                    f,
                    sep=";",
                    encoding="latin1",
                    usecols=usecols,
                    chunksize=200_000,
                    low_memory=False,
                )

                for chunk in chunks:
                    chunk = chunk.dropna(subset=["SG_UF", "NM_MUNICIPIO", "NR_ZONA", "QT_ELEITORES"])
                    if chunk.empty:
                        continue

                    chunk["SG_UF"] = chunk["SG_UF"].astype(str).str.strip().str.upper()
                    chunk = chunk[chunk["SG_UF"] == uf]
                    if chunk.empty:
                        continue

                    chunk["NM_MUNICIPIO"] = chunk["NM_MUNICIPIO"].astype(str).str.strip()
                    chunk["NR_ZONA"] = pd.to_numeric(chunk["NR_ZONA"], errors="coerce").fillna(0).astype(int)
                    chunk = chunk[chunk["NR_ZONA"] > 0]
                    if chunk.empty:
                        continue

                    chunk["QT_ELEITORES"] = pd.to_numeric(chunk["QT_ELEITORES"], errors="coerce").fillna(0).astype(int)
                    chunk["DS_GENERO"] = chunk["DS_GENERO"].astype(str).str.upper()

                    if "DT_GERACAO" in chunk.columns:
                        datas_geracao.update(
                            chunk["DT_GERACAO"].dropna().astype(str).str.strip().tolist()
                        )

                    # Canoniza nome para alinhar com IBGE
                    chunk["MUN_CANON"] = chunk["NM_MUNICIPIO"].apply(
                        lambda n: canon_por_uf_norm.get((uf, normalizar_nome(n)), n.title())
                    )

                    keys = ["SG_UF", "MUN_CANON", "NR_ZONA"]

                    g_total = chunk.groupby(keys, as_index=False)["QT_ELEITORES"].sum()
                    for _, row in g_total.iterrows():
                        k = (row["SG_UF"], row["MUN_CANON"], int(row["NR_ZONA"]))
                        agg_total[k] += int(row["QT_ELEITORES"])

                    fem = chunk[chunk["DS_GENERO"].str.contains("FEMIN", na=False)]
                    if not fem.empty:
                        g_fem = fem.groupby(keys, as_index=False)["QT_ELEITORES"].sum()
                        for _, row in g_fem.iterrows():
                            k = (row["SG_UF"], row["MUN_CANON"], int(row["NR_ZONA"]))
                            agg_fem[k] += int(row["QT_ELEITORES"])

                    masc = chunk[chunk["DS_GENERO"].str.contains("MASCUL", na=False)]
                    if not masc.empty:
                        g_masc = masc.groupby(keys, as_index=False)["QT_ELEITORES"].sum()
                        for _, row in g_masc.iterrows():
                            k = (row["SG_UF"], row["MUN_CANON"], int(row["NR_ZONA"]))
                            agg_masc[k] += int(row["QT_ELEITORES"])

                    secoes_chunk = chunk[["SG_UF", "MUN_CANON", "NR_ZONA", "NR_SECAO"]].dropna()
                    if not secoes_chunk.empty:
                        secoes_chunk["NR_SECAO"] = pd.to_numeric(
                            secoes_chunk["NR_SECAO"], errors="coerce"
                        ).fillna(0).astype(int)
                        secoes_chunk = secoes_chunk[secoes_chunk["NR_SECAO"] > 0].drop_duplicates()
                        for _, row in secoes_chunk.iterrows():
                            kz = (row["SG_UF"], row["MUN_CANON"], int(row["NR_ZONA"]))
                            secoes_por_zona[kz].add(int(row["NR_SECAO"]))

                    # Perfil municipal real para estratificação
                    pcols = ["SG_UF", "MUN_CANON", "DS_GENERO", "DS_GRAU_INSTRUCAO", "DS_FAIXA_ETARIA", "QT_ELEITORES"]
                    p = chunk[pcols].copy()
                    p["DS_GENERO"] = p["DS_GENERO"].fillna("N/D").astype(str).str.strip()
                    p["DS_GRAU_INSTRUCAO"] = p["DS_GRAU_INSTRUCAO"].fillna("N/D").astype(str).str.strip()
                    p["DS_FAIXA_ETARIA"] = p["DS_FAIXA_ETARIA"].fillna("N/D").astype(str).str.strip()

                    g_gen = p.groupby(["SG_UF", "MUN_CANON", "DS_GENERO"], as_index=False)["QT_ELEITORES"].sum()
                    for _, row in g_gen.iterrows():
                        k = (row["SG_UF"], row["MUN_CANON"], "GENERO", str(row["DS_GENERO"]))
                        perfil_municipal[k] += int(row["QT_ELEITORES"])

                    g_ins = p.groupby(["SG_UF", "MUN_CANON", "DS_GRAU_INSTRUCAO"], as_index=False)["QT_ELEITORES"].sum()
                    for _, row in g_ins.iterrows():
                        k = (row["SG_UF"], row["MUN_CANON"], "INSTRUCAO", str(row["DS_GRAU_INSTRUCAO"]))
                        perfil_municipal[k] += int(row["QT_ELEITORES"])

                    g_fa = p.groupby(["SG_UF", "MUN_CANON", "DS_FAIXA_ETARIA"], as_index=False)["QT_ELEITORES"].sum()
                    for _, row in g_fa.iterrows():
                        k = (row["SG_UF"], row["MUN_CANON"], "FAIXA_ETARIA", str(row["DS_FAIXA_ETARIA"]))
                        perfil_municipal[k] += int(row["QT_ELEITORES"])

            linhas = []
            for k, total in agg_total.items():
                linhas.append(
                    {
                        "UF": k[0],
                        "MUNICIPIO": k[1],
                        "ZONA": k[2],
                        "ELEITORES_TOTAL": int(total),
                        "ELEITORES_FEMININO": int(agg_fem.get(k, 0)),
                        "ELEITORES_MASCULINO": int(agg_masc.get(k, 0)),
                        "SECOES": int(len(secoes_por_zona.get(k, set()))),
                    }
                )

            print(f"   ↳ {uf}: {len(linhas):,} zonas agregadas")
            linhas_perfil = []
            for k, qt in perfil_municipal.items():
                linhas_perfil.append(
                    {
                        "UF": k[0],
                        "MUNICIPIO": k[1],
                        "DIMENSAO": k[2],
                        "CATEGORIA": k[3],
                        "QT_ELEITORES": int(qt),
                    }
                )
            return linhas, datas_geracao, linhas_perfil
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def montar_base_tse(df_ibge: pd.DataFrame, ufs_filtro: set[str] | None = None) -> tuple[pd.DataFrame, set[str], pd.DataFrame]:
    """Gera DataFrame TSE agregado por município/zona com dados reais."""
    recursos = buscar_recursos_tse_por_uf()
    if ufs_filtro:
        recursos = {uf: url for uf, url in recursos.items() if uf in ufs_filtro}

    canon = {
        (row["UF"], normalizar_nome(row["MUNICIPIO"])): row["MUNICIPIO"]
        for _, row in df_ibge[["UF", "MUNICIPIO"]].iterrows()
    }

    todas_linhas: list[dict] = []
    todas_linhas_perfil: list[dict] = []
    datas_geracao_tse: set[str] = set()

    print("🌐 TSE: baixando e agregando eleitorado por seção/município/zona...")
    for uf in sorted(recursos.keys()):
        url = recursos[uf]
        linhas_uf, datas_uf, linhas_perfil_uf = processar_arquivo_tse_uf(uf, url, canon)
        todas_linhas.extend(linhas_uf)
        todas_linhas_perfil.extend(linhas_perfil_uf)
        datas_geracao_tse.update(datas_uf)

    df_tse = pd.DataFrame(todas_linhas)
    if df_tse.empty:
        raise RuntimeError("Base TSE resultou vazia. Verifique conectividade e fontes.")

    # Sanidade: garantir inteiros e consistência mínima de gênero
    for col in [
        "ELEITORES_TOTAL",
        "ELEITORES_FEMININO",
        "ELEITORES_MASCULINO",
        "SECOES",
        "ZONA",
    ]:
        df_tse[col] = pd.to_numeric(df_tse[col], errors="coerce").fillna(0).astype(int)

    # Se total de gênero vier incompleto em algum estrato, completa por diferença
    soma_genero = df_tse["ELEITORES_FEMININO"] + df_tse["ELEITORES_MASCULINO"]
    faltante = df_tse["ELEITORES_TOTAL"] - soma_genero
    mask_faltante = faltante > 0
    if mask_faltante.any():
        df_tse.loc[mask_faltante, "ELEITORES_FEMININO"] += faltante[mask_faltante]

    df_tse = df_tse.sort_values(["UF", "MUNICIPIO", "ZONA"]).reset_index(drop=True)
    df_perfil = pd.DataFrame(todas_linhas_perfil)
    if not df_perfil.empty:
        df_perfil = (
            df_perfil.groupby(["UF", "MUNICIPIO", "DIMENSAO", "CATEGORIA"], as_index=False)["QT_ELEITORES"]
            .sum()
            .sort_values(["UF", "MUNICIPIO", "DIMENSAO", "CATEGORIA"])
            .reset_index(drop=True)
        )

    return df_tse, datas_geracao_tse, df_perfil


def salvar_metadados(ano_ibge: int, datas_tse: set[str]):
    """Salva metadados de referência das bases geradas."""
    caminho = os.path.join(DADOS_DIR, "meta_fontes.json")
    meta = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "ibge": {
            "fonte": "API IBGE Agregados 6579 / variável 9324",
            "url": IBGE_POP_URL,
            "ano_referencia": ano_ibge,
        },
        "tse": {
            "fonte": "Dados Abertos TSE - Eleitorado Atual (perfil por seção)",
            "catalogo_url": TSE_CKAN_SEARCH_URL,
            "datas_geracao_detectadas": sorted(datas_tse),
        },
    }

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera dados reais (IBGE + TSE) para o Instituto Amostral"
    )
    parser.add_argument(
        "--ufs",
        type=str,
        default="",
        help="Lista de UFs separadas por vírgula para processamento parcial (ex: TO,SP)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    ufs_filtro = {
        uf.strip().upper()
        for uf in args.ufs.split(",")
        if uf.strip()
    }
    if not ufs_filtro:
        ufs_filtro = None

    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║   Instituto Amostral — Gerador de Dados Reais (IBGE + TSE)       ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()

    # 1) IBGE
    df_ibge, ano_ibge = montar_base_ibge()

    # 2) TSE
    df_tse, datas_tse, df_tse_perfil = montar_base_tse(df_ibge, ufs_filtro=ufs_filtro)

    # Se filtro por UF foi aplicado, mantém IBGE compatível com TSE gerado
    if ufs_filtro:
        df_ibge = df_ibge[df_ibge["UF"].isin(ufs_filtro)].copy()

    # 3) Salva arquivos
    caminho_ibge = os.path.join(DADOS_DIR, "ibge.csv")
    caminho_tse = os.path.join(DADOS_DIR, "tse.csv")
    caminho_tse_perfil = os.path.join(DADOS_DIR, "tse_perfil.csv")

    df_ibge.to_csv(caminho_ibge, index=False, encoding="utf-8-sig")
    df_tse.to_csv(caminho_tse, index=False, encoding="utf-8-sig")
    if not df_tse_perfil.empty:
        df_tse_perfil.to_csv(caminho_tse_perfil, index=False, encoding="utf-8-sig")
    salvar_metadados(ano_ibge, datas_tse)

    # 4) Resumo
    print()
    print("📊 Resumo final")
    print(f"   IBGE: {len(df_ibge):,} municípios")
    print(f"   TSE : {len(df_tse):,} zonas eleitorais agregadas")
    if not df_tse_perfil.empty:
        print(f"   TSE Perfil: {len(df_tse_perfil):,} linhas municipais de estratificação")
    print(f"   Arquivos: {caminho_ibge} | {caminho_tse}")
    print(f"   Referência IBGE: {ano_ibge}")
    if datas_tse:
        print(f"   Datas TSE detectadas: {', '.join(sorted(datas_tse)[:3])}{' ...' if len(datas_tse) > 3 else ''}")
    print()


if __name__ == "__main__":
    main()
