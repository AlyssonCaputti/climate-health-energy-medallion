"""Modelos: quanto o clima antecipa a dengue e como o solar se espalha entre os municípios."""

import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import curve_fit

from db import get_engine

LAGS = np.arange(1, 9)


def base_polinomial(df, prefixo, grau=2):
    # Lags vizinhos são quase iguais (colinearidade). Em vez de 8 coeficientes nervosos,
    # forço o efeito a seguir uma curva suave: é a ideia do lag polinomial de Almon.
    return pd.DataFrame({
        f"{prefixo}_p{g}": sum(df[f"{prefixo}_lag{lag}"] * lag**g for lag in LAGS)
        for g in range(grau + 1)
    })


def efeito_por_lag(params, prefixo, grau=2):
    # Volto da curva para o efeito de cada semana, em % de casos por +1 unidade.
    g = params[[f"{prefixo}_p{i}" for i in range(grau + 1)]].to_numpy()
    beta = sum(g[i] * LAGS**i for i in range(grau + 1))
    return (np.exp(beta) - 1) * 100


def bass(t, m, p, q):
    # m = mercado potencial, p = inovação (adota sozinho), q = imitação (adota porque o vizinho adotou).
    e = np.exp(-(p + q) * t)
    return m * (1 - e) / (1 + (q / p) * e)


def ajustar_bass(y):
    # Limites realistas: o potencial nunca é menor do que o que já foi instalado.
    t = np.arange(len(y))
    (m, p, q), _ = curve_fit(
        bass, t, y,
        p0=[y[-1] * 1.5, 0.0005, 0.05],
        bounds=([y[-1], 1e-7, 1e-4], [y[-1] * 20, 0.1, 1]),
        maxfev=20_000,
    )
    return m, p, q


def modelo_dengue_clima(engine):
    df = pd.read_sql("SELECT * FROM gold.dengue_features", engine)
    lags_clima = [f"{v}_lag{lag}" for v in ("temp_med", "umid_med") for lag in LAGS]
    df = df.dropna(subset=lags_clima + ["casos_lag1", "populacao"])
    # O offset é log(população): zero viraria -inf e contaminaria o ajuste inteiro.
    df = df[df["populacao"] > 0]

    X = pd.concat([base_polinomial(df, "temp_med"), base_polinomial(df, "umid_med")], axis=1)
    X["log_casos_lag1"] = np.log1p(df["casos_lag1"])  # inércia da epidemia
    X = sm.add_constant(X)

    # Casos são contagem com muita variância: Binomial Negativa. O offset vira tudo em taxa
    # por habitante, aí Curitiba e uma cidade de 3 mil pessoas ficam comparáveis.
    modelo = sm.GLM(
        df["casos_notificados"], X,
        family=sm.families.NegativeBinomial(alpha=1.0),
        offset=np.log(df["populacao"]),
    ).fit()

    efeitos = pd.DataFrame({"lag_semanas": LAGS})
    for v in ("temp_med", "umid_med"):
        efeitos[f"efeito_{v}_pct"] = efeito_por_lag(modelo.params, v)

    print(efeitos.round(2).to_string(index=False))
    print(f"n={len(df)} | pseudo-R²={modelo.pseudo_rsquared():.3f}")
    efeitos.to_sql("ml_dengue_efeito_clima", engine, schema="gold", if_exists="replace", index=False)


def modelo_bass_solar(engine):
    df = pd.read_sql("SELECT * FROM gold.solar_adocao_mensal", engine)

    resultados = []
    for cod, serie in df.groupby("cod_municipio"):
        y = serie["instalacoes_acum"].to_numpy(dtype=float)
        if y[-1] < 100:  # pouca instalação = curva sem forma, ajuste não diz nada
            continue
        try:
            m, p, q = ajustar_bass(y)
        except RuntimeError:  # não convergiu? sigo pro próximo município
            continue
        resultados.append({
            "cod_municipio": cod, "potencial_m": m, "inovacao_p": p, "imitacao_q": q,
            "instalacoes_atuais": y[-1], "saturacao_pct": y[-1] / m * 100,
        })

    res = pd.DataFrame(resultados)
    print(f"{len(res)} municípios ajustados")
    print(res[["inovacao_p", "imitacao_q", "saturacao_pct"]].describe().round(4).to_string())
    res.to_sql("ml_solar_bass", engine, schema="gold", if_exists="replace", index=False)


MODELOS = {"dengue": modelo_dengue_clima, "solar": modelo_bass_solar}


if __name__ == "__main__":
    engine = get_engine()
    for nome in sys.argv[1:] or MODELOS:
        MODELOS[nome](engine)
