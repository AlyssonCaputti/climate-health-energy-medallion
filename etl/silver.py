"""Silver: limpo, tipo, deduplico e valido. Separo transformação (pura) de leitura/escrita (banco)."""

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

COLUNAS_SOLAR = {
    "codempreendimento": "cod_empreendimento",
    "codmunicipioibge": "cod_municipio",
    # O arquivo não tem data de conexão. A única data é a da última atualização cadastral,
    # e é ela que uso como aproximação do momento da instalação (ver README).
    "dthatualizacadastralempreend": "data_cadastro",
    "dscclasseconsumo": "classe_consumo",
    "sigtipoconsumidor": "tipo_consumidor",
    "dscporte": "porte",
    "mdapotenciainstaladakw": "potencia_kw",
    "qtducrecebecredito": "ucs_credito",
}


# --- transformações puras: entram DataFrames, saem DataFrames. É isso que os testes cobrem. ---


def validar(condicao, mensagem):
    # Não uso assert: com "python -O" ele some e o dado sujo passa direto pro gold.
    if not condicao:
        raise ValueError(mensagem)


def transformar_dim_municipio(bronze):
    # Uso a hierarquia "região imediata" (IBGE 2017). A antiga (microrregião) vem nula
    # para Boa Esperança do Norte/MT, município criado em 2025.
    dim = bronze[list(COLUNAS_MUNICIPIO)].rename(columns=COLUNAS_MUNICIPIO)
    dim["municipio"] = dim["municipio"].str.strip()

    validar(dim["cod_municipio"].is_unique, "cod_municipio duplicado")
    validar(dim.notna().all().all(), "dim_municipio com nulos")
    return dim


def transformar_fato_dengue(bronze):
    fato = bronze[list(COLUNAS_DENGUE)].rename(columns=COLUNAS_DENGUE)
    fato["data_inicio_semana"] = pd.to_datetime(fato["data_inicio_semana"])

    # A semana vem como 202552. Divisão inteira e resto separam ano e semana sem gambiarra de texto.
    fato["ano"] = fato["semana_epi"] // 100
    fato["semana"] = fato["semana_epi"] % 100

    # Granularidade da fato: uma linha por município por semana.
    fato = fato.drop_duplicates(subset=["cod_municipio", "semana_epi"])
    fato = fato.sort_values(["cod_municipio", "data_inicio_semana"]).reset_index(drop=True)

    # Clima fica fora da validação: ~1% das semanas não tem estação, e tudo bem.
    chaves = ["cod_municipio", "semana_epi", "casos_notificados"]
    validar(fato[chaves].notna().all().all(), "chave ou casos nulos")
    validar((fato["casos_notificados"] >= 0).all(), "casos negativos")
    return fato


def transformar_fato_solar(bronze):
    # UFV = usina fotovoltaica. O resto (termelétrica, eólica, hidro) não entra nessa análise.
    solar = bronze[bronze["sigtipogeracao"] == "UFV"]
    fato = solar[list(COLUNAS_SOLAR)].rename(columns=COLUNAS_SOLAR)

    fato["cod_municipio"] = pd.to_numeric(fato["cod_municipio"], errors="coerce").astype("Int64")
    fato["data_cadastro"] = pd.to_datetime(fato["data_cadastro"], errors="coerce")
    # Decimal brasileiro: "32,50" → 32.5. E ",48" (sem o zero) também vira 0.48.
    fato["potencia_kw"] = pd.to_numeric(fato["potencia_kw"].str.replace(",", "."), errors="coerce")
    fato["ucs_credito"] = pd.to_numeric(fato["ucs_credito"], errors="coerce").astype("Int64")
    fato = fato.drop_duplicates(subset=["cod_empreendimento"])

    # Achei instalações cadastradas com ",00" kW. Painel que não gera nada não é painel.
    invalidas = fato["potencia_kw"] <= 0
    print(f"removidas {invalidas.sum()} instalações com potência <= 0")
    fato = fato[~invalidas].reset_index(drop=True)

    # Data que não converteu vira NaT, e o groupby mensal do gold descartaria a linha calado.
    sem_data = fato["data_cadastro"].isna()
    print(f"removidas {sem_data.sum()} instalações com data inválida")
    fato = fato[~sem_data].reset_index(drop=True)

    validar(fato["cod_municipio"].notna().all(), "município nulo")
    validar((fato["potencia_kw"] > 0).all(), "potência inválida")
    return fato


# --- leitura e escrita: a parte chata, isolada aqui. ---


def construir_dim_municipio(engine):
    bronze = pd.read_sql("SELECT * FROM bronze.ibge_municipios", engine)
    dim = transformar_dim_municipio(bronze)
    dim.to_sql("dim_municipio", engine, schema="silver", if_exists="replace", index=False)
    print(f"silver.dim_municipio: {len(dim)} linhas")


def construir_fato_dengue_semanal(engine):
    bronze = pd.read_sql("SELECT * FROM bronze.infodengue", engine)
    fato = transformar_fato_dengue(bronze)
    fato.to_sql("fato_dengue_semanal", engine, schema="silver", if_exists="replace", index=False, chunksize=10_000)
    print(f"silver.fato_dengue_semanal: {len(fato)} linhas")


def construir_fato_solar_instalacao(engine):
    bronze = pd.read_sql("SELECT * FROM bronze.aneel_gd", engine)
    fato = transformar_fato_solar(bronze)
    fato.to_sql("fato_solar_instalacao", engine, schema="silver", if_exists="replace", index=False, chunksize=10_000)
    print(f"silver.fato_solar_instalacao: {len(fato)} linhas")


ETAPAS = {
    "municipio": construir_dim_municipio,
    "dengue": construir_fato_dengue_semanal,
    "solar": construir_fato_solar_instalacao,
}


if __name__ == "__main__":
    engine = get_engine()
    for nome in sys.argv[1:] or ETAPAS:
        ETAPAS[nome](engine)
