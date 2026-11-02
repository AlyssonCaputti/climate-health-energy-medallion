import sys

import pandas as pd

from db import get_engine

COLUNAS_MUNICIPIO = {
    "id": "cod_municipio",
    "nome": "municipio",
    "regiao_imediata_regiao_intermediaria_uf_id": "cod_uf",
    "regiao_imediata_regiao_intermediaria_uf_sigla": "uf",
    "regiao_imediata_regiao_intermediaria_uf_nome": "uf_nome",
    "regiao_imediata_regiao_intermediaria_uf_regiao_sigla": "regiao",
    "regiao_imediata_regiao_intermediaria_nome": "regiao_intermediaria",
    "regiao_imediata_nome": "regiao_imediata",
}

COLUNAS_SOLAR = {
    "codempreendimento": "cod_empreendimento",
    "codmunicipioibge": "cod_municipio",
    "dthatualizacadastralempreend": "data_conexao",
    "dscclassecosumo": "classe_consumo",
    "sigtipoconsumidor": "tipo_consumidor",
    "dscporte": "porte",
    "mdapotenciainstaladakw": "potencia_kw",
    "qtducrecebecredito": "ucs_credito",
}


COLUNAS_DENGUE = {
    "cod_municipio": "cod_municipio",
    "data_inise": "data_inicio_semana",
    "se": "semana_epi",
    "casos": "casos_notificados",
    "casos_est": "casos_estimados",
    "p_inc100k": "incidencia_100k",
    "rt": "rt",
    "nivel": "nivel_alerta",
    "pop": "populacao",
    "tempmin": "temp_min",
    "tempmed": "temp_med",
    "tempmax": "temp_max",
    "umidmin": "umid_min",
    "umidmed": "umid_med",
    "umidmax": "umid_max",
}


def construir_fato_dengue_semanal(engine):
    bronze = pd.read_sql("SELECT * FROM bronze.infodengue", engine)

    fato = bronze[list(COLUNAS_DENGUE)].rename(columns=COLUNAS_DENGUE)
    fato["data_inicio_semana"] = pd.to_datetime(fato["data_inicio_semana"])
    fato["ano"] = fato["semana_epi"] // 100
    fato["semana"] = fato["semana_epi"] % 100
    fato = fato.drop_duplicates(subset=["cod_municipio", "semana_epi"])
    fato = fato.sort_values(["cod_municipio", "data_inicio_semana"])

    chaves = ["cod_municipio", "semana_epi", "casos_notificados"]
    assert fato[chaves].notna().all().all(), "chave ou casos nulos"
    assert (fato["casos_notificados"] >= 0).all(), "casos negativos"

    fato.to_sql("fato_dengue_semanal", engine, schema="silver", if_exists="replace", index=False, chunksize=10_000)
    print(f"silver.fato_dengue_semanal: {len(fato)} linhas")


def construir_fato_solar_instalacao(engine):
    bronze = pd.read_sql("SELECT * FROM bronze.aneel_gd WHERE sigtipogeracao = 'UFV'", engine)

    fato = bronze[list(COLUNAS_SOLAR)].rename(columns=COLUNAS_SOLAR)
    fato["cod_municipio"] = pd.to_numeric(fato["cod_municipio"], errors="coerce").astype("Int64")
    fato["data_conexao"] = pd.to_datetime(fato["data_conexao"], errors="coerce")
    fato["potencia_kw"] = pd.to_numeric(fato["potencia_kw"].str.replace(",", "."), errors="coerce")
    fato["ucs_credito"] = pd.to_numeric(fato["ucs_credito"], errors="coerce").astype("Int64")
    fato = fato.drop_duplicates(subset=["cod_empreendimento"])

    print("nulos após conversão:", fato.isna().sum()[lambda s: s > 0].to_dict())
    assert fato["cod_municipio"].notna().all(), "município nulo"
    assert (fato["potencia_kw"] > 0).all(), "potência inválida"

    fato.to_sql("fato_solar_instalacao", engine, schema="silver", if_exists="replace", index=False, chunksize=10_000)
    print(f"silver.fato_solar_instalacao: {len(fato)} linhas")


def construir_dim_municipio(engine):
    bronze = pd.read_sql("SELECT * FROM bronze.ibge_municipios", engine)

    dim = bronze[list(COLUNAS_MUNICIPIO)].rename(columns=COLUNAS_MUNICIPIO)
    dim["municipio"] = dim["municipio"].str.strip()

    assert dim["cod_municipio"].is_unique, "cod_municipio duplicado"
    assert dim.notna().all().all(), "dim_municipio com nulos"

    dim.to_sql("dim_municipio", engine, schema="silver", if_exists="replace", index=False)
    print(f"silver.dim_municipio: {len(dim)} linhas")


if __name__ == "__main__":
    engine = get_engine()
    etapas = {
        "municipio": construir_dim_municipio,
        "dengue": construir_fato_dengue_semanal,
        "solar": construir_fato_solar_instalacao,
    }
    for nome in sys.argv[1:] or etapas:
        etapas[nome](engine)
