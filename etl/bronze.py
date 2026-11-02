"""Bronze: trago cada fonte do jeito que ela veio, só com metadados de linhagem."""

import io
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from db import get_engine

URL_IBGE_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
URL_INFODENGUE = "https://info.dengue.mat.br/api/alertcity"
URL_ANEEL_GD = "https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-b622-40438d40aba2/resource/b1bd71e7-d0ad-4214-9053-cbd58e9564a7/download/empreendimento-geracao-distribuida.csv"
ARQUIVO_ANEEL_GD = Path("/data/raw/aneel_gd.zip")


def carimbar(df, fonte):
    # Toda tabela bronze sabe de onde veio e quando entrou. Salva vidas no debug.
    df["_fonte"] = fonte
    df["_ingerido_em"] = datetime.now(timezone.utc)
    return df


def baixar(url, destino):
    # Se já baixei, reaproveito. O arquivo da ANEEL tem 110 MB e não muda toda hora.
    if destino.exists():
        print(f"usando cache: {destino}")
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    # stream=True escreve em blocos de 1 MB, sem segurar o arquivo inteiro na memória.
    with requests.get(url, stream=True, timeout=300) as resposta:
        resposta.raise_for_status()
        with open(destino, "wb") as arquivo:
            for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                arquivo.write(bloco)
    print(f"baixado: {destino} ({destino.stat().st_size / 1e6:.0f} MB)")


def ingerir_ibge_municipios(engine):
    resposta = requests.get(URL_IBGE_MUNICIPIOS, timeout=60)
    resposta.raise_for_status()

    # O JSON é aninhado (município → região → UF). Achato e deixo os nomes amigáveis pro SQL.
    df = pd.json_normalize(resposta.json())
    df.columns = df.columns.str.replace(r"[.-]", "_", regex=True).str.lower()

    carimbar(df, URL_IBGE_MUNICIPIOS).to_sql(
        "ibge_municipios", engine, schema="bronze", if_exists="replace", index=False
    )
    print(f"bronze.ibge_municipios: {len(df)} linhas")


def ingerir_infodengue(engine, limite=None):
    uf = os.environ["UF"]
    ano_inicio = int(os.environ["ANO_INICIO"])
    ano_fim = datetime.now().year

    # Leio a lista de municípios do próprio bronze: camada nenhuma depende de uma camada acima.
    municipios = pd.read_sql("SELECT * FROM bronze.ibge_municipios", engine)
    codigos = municipios.loc[
        municipios["regiao_imediata_regiao_intermediaria_uf_sigla"] == uf, "id"
    ].head(limite)

    partes = []
    falhas = []
    for cod in codigos:
        params = {
            "geocode": cod, "disease": "dengue", "format": "csv",
            "ew_start": 1, "ew_end": 53, "ey_start": ano_inicio, "ey_end": ano_fim,
        }
        # Um município com problema não pode derrubar os outros 398.
        try:
            resposta = requests.get(URL_INFODENGUE, params=params, timeout=60)
            resposta.raise_for_status()
            df = pd.read_csv(io.StringIO(resposta.text))
        except (requests.RequestException, pd.errors.EmptyDataError) as erro:
            falhas.append(cod)
            print(f"falha {cod}: {erro}")
            continue

        # A API devolve Localidade_id = 0, então eu mesmo marco de qual município é.
        df["cod_municipio"] = cod
        partes.append(df)
        time.sleep(0.2)  # API pública: sem pressa, sem bloqueio.

    df = pd.concat(partes, ignore_index=True)
    df.columns = df.columns.str.lower()

    carimbar(df, URL_INFODENGUE).to_sql(
        "infodengue", engine, schema="bronze", if_exists="replace", index=False, chunksize=10_000
    )
    print(f"bronze.infodengue: {len(df)} linhas, {len(partes)} municípios, {len(falhas)} falhas")


def ingerir_aneel_gd(engine):
    uf = os.environ["UF"]
    baixar(URL_ANEEL_GD, ARQUIVO_ANEEL_GD)

    # São 1,5 GB descompactados. Leio direto do zip, em pedaços, e só guardo a UF que me interessa.
    # dtype=str de propósito: conversão de tipo é trabalho do silver.
    partes = []
    for pedaco in pd.read_csv(ARQUIVO_ANEEL_GD, sep=";", dtype=str, chunksize=200_000):
        partes.append(pedaco[pedaco["SigUF"] == uf])

    df = pd.concat(partes, ignore_index=True)
    df.columns = df.columns.str.lower()

    carimbar(df, URL_ANEEL_GD).to_sql(
        "aneel_gd", engine, schema="bronze", if_exists="replace", index=False, chunksize=10_000
    )
    print(f"bronze.aneel_gd: {len(df)} linhas")


FONTES = {
    "ibge": ingerir_ibge_municipios,
    "infodengue": ingerir_infodengue,
    "aneel": ingerir_aneel_gd,
}


if __name__ == "__main__":
    # python bronze.py infodengue → roda só essa. Sem argumento, roda todas.
    engine = get_engine()
    for nome in sys.argv[1:] or FONTES:
        FONTES[nome](engine)
