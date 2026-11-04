import pandas as pd

from gold import adicionar_lags, calcular_adocao_mensal


def test_lags_nao_vazam_entre_municipios():
    df = pd.DataFrame({
        "cod_municipio": [1, 1, 2, 2],
        "data_inicio_semana": pd.to_datetime(["2025-01-05", "2025-01-12"] * 2),
        "temp_med": [20.0, 21.0, 30.0, 31.0],
        "umid_med": [70.0, 71.0, 80.0, 81.0],
        "casos_notificados": [5, 6, 50, 60],
    })
    res = adicionar_lags(df)

    # A primeira semana do município 2 não pode herdar a temperatura do município 1.
    primeira_do_2 = res[res["cod_municipio"] == 2].iloc[0]
    assert pd.isna(primeira_do_2["temp_med_lag1"])
    assert res[res["cod_municipio"] == 2].iloc[1]["temp_med_lag1"] == 30.0


def test_lags_respeitam_semana_faltando():
    # A semana de 12/01 não veio. O lag de 1 semana da semana de 19/01 tem que ser vazio, não 05/01.
    df = pd.DataFrame({
        "cod_municipio": [1, 1],
        "data_inicio_semana": pd.to_datetime(["2025-01-05", "2025-01-19"]),
        "temp_med": [20.0, 22.0],
        "umid_med": [70.0, 72.0],
        "casos_notificados": [5, 7],
    })
    res = adicionar_lags(df)

    ultima = res.iloc[1]
    assert pd.isna(ultima["temp_med_lag1"])
    assert pd.isna(ultima["casos_lag1"])
    assert ultima["temp_med_lag2"] == 20.0


def test_adocao_preenche_meses_vazios_e_acumula():
    inst = pd.DataFrame({
        "cod_municipio": [1, 1],
        "data_cadastro": pd.to_datetime(["2024-01-10", "2024-03-20"]),  # fevereiro sem nada
        "potencia_kw": [5.0, 10.0],
    })
    pop = pd.DataFrame({"cod_municipio": [1], "populacao": [1000]})

    res = calcular_adocao_mensal(inst, pop)

    assert res["novas_instalacoes"].tolist() == [1, 0, 1]
    assert res["instalacoes_acum"].tolist() == [1, 1, 2]
    assert res["instalacoes_por_mil_hab"].iloc[-1] == 2.0
