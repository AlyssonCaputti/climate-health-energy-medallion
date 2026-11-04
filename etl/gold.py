"""Gold: tabelas prontas pra responder pergunta e alimentar modelo."""

import sys

import pandas as pd

from db import get_engine

LAGS_CLIMA = range(1, 9)


def semanas_atras(df, coluna, n):
    # Busco pela data, não pela posição: se faltar uma semana na série, o lag não escorrega.
    # A chave inclui o município, então a última semana de um não vaza pro próximo.
    chave = ["cod_municipio", "data_inicio_semana"]
    passado = df[chave + [coluna]].copy()
    passado["data_inicio_semana"] += pd.Timedelta(weeks=n)
    return df[chave].merge(passado, on=chave, how="left")[coluna].to_numpy()


def adicionar_lags(df):
    # O mosquito responde ao clima com semanas de atraso, então crio "o clima de N semanas atrás".
    df = df.sort_values(["cod_municipio", "data_inicio_semana"]).reset_index(drop=True)
    for lag in LAGS_CLIMA:
        df[f"temp_med_lag{lag}"] = semanas_atras(df, "temp_med", lag)
        df[f"umid_med_lag{lag}"] = semanas_atras(df, "umid_med", lag)
    df["casos_lag1"] = semanas_atras(df, "casos_notificados", 1)
    return df


def calcular_adocao_mensal(inst, pop):
    inst = inst.copy()
    inst["mes"] = inst["data_cadastro"].dt.to_period("M").dt.to_timestamp()
    mensal = (
        inst.groupby(["cod_municipio", "mes"])
        .agg(novas_instalacoes=("potencia_kw", "size"), nova_potencia_kw=("potencia_kw", "sum"))
        .reset_index()
    )

    # Mês sem instalação some do groupby. Monto a grade município × mês e preencho com zero,
    # porque o modelo de difusão precisa de série contínua.
    meses = pd.date_range(mensal["mes"].min(), mensal["mes"].max(), freq="MS")
    grade = pd.MultiIndex.from_product([mensal["cod_municipio"].unique(), meses], names=["cod_municipio", "mes"])
    mensal = mensal.set_index(["cod_municipio", "mes"]).reindex(grade, fill_value=0).reset_index()

    grupo = mensal.groupby("cod_municipio")
    mensal["instalacoes_acum"] = grupo["novas_instalacoes"].cumsum()
    mensal["potencia_acum_kw"] = grupo["nova_potencia_kw"].cumsum()

    mensal = mensal.merge(pop, on="cod_municipio", how="left")
    mensal["instalacoes_por_mil_hab"] = mensal["instalacoes_acum"] / mensal["populacao"] * 1000
    return mensal


def construir_dengue_features(engine):
    df = pd.read_sql("SELECT * FROM silver.fato_dengue_semanal", engine)
    dim = pd.read_sql("SELECT cod_municipio, municipio, regiao_imediata FROM silver.dim_municipio", engine)

    df = adicionar_lags(df.merge(dim, on="cod_municipio", how="left"))
    df.to_sql("dengue_features", engine, schema="gold", if_exists="replace", index=False, chunksize=10_000)
    print(f"gold.dengue_features: {len(df)} linhas, {df.shape[1]} colunas")


def construir_solar_adocao_mensal(engine):
    inst = pd.read_sql("SELECT cod_municipio, data_cadastro, potencia_kw FROM silver.fato_solar_instalacao", engine)
    # Reaproveito a população que já vem no InfoDengue: uma fonte a menos pra manter.
    pop = pd.read_sql(
        "SELECT DISTINCT ON (cod_municipio) cod_municipio, populacao "
        "FROM silver.fato_dengue_semanal ORDER BY cod_municipio, data_inicio_semana DESC",
        engine,
    )

    mensal = calcular_adocao_mensal(inst, pop)
    mensal.to_sql("solar_adocao_mensal", engine, schema="gold", if_exists="replace", index=False, chunksize=10_000)
    print(f"gold.solar_adocao_mensal: {len(mensal)} linhas")


ETAPAS = {
    "dengue": construir_dengue_features,
    "solar": construir_solar_adocao_mensal,
}


if __name__ == "__main__":
    engine = get_engine()
    for nome in sys.argv[1:] or ETAPAS:
        ETAPAS[nome](engine)
