import pandas as pd
import pytest

from silver import transformar_dim_municipio, transformar_fato_dengue, transformar_fato_solar

PREFIXO = "regiao_imediata_regiao_intermediaria"


def bronze_municipios(ids, nomes):
    # Monto só as colunas que o silver usa. As de microrregião nem entram, e é esse o ponto.
    return pd.DataFrame({
        "id": ids,
        "nome": nomes,
        f"{PREFIXO}_uf_id": 51,
        f"{PREFIXO}_uf_sigla": "MT",
        f"{PREFIXO}_uf_nome": "Mato Grosso",
        f"{PREFIXO}_uf_regiao_sigla": "CO",
        f"{PREFIXO}_nome": "Sinop",
        "regiao_imediata_nome": "Sorriso",
    })


def test_dim_municipio_limpa_nomes():
    dim = transformar_dim_municipio(bronze_municipios([5101837], ["  Boa Esperança do Norte "]))
    assert dim.loc[0, "municipio"] == "Boa Esperança do Norte"
    assert dim.loc[0, "uf"] == "MT"


def test_dim_municipio_barra_codigo_duplicado():
    with pytest.raises(AssertionError, match="duplicado"):
        transformar_dim_municipio(bronze_municipios([1, 1], ["A", "B"]))


def bronze_dengue(**sobrescritas):
    linha = {
        "cod_municipio": 4106902, "data_inise": "2025-12-21", "se": 202552,
        "casos": 10, "casos_est": 12.0, "p_inc100k": 0.5, "rt": 1.1, "nivel": 1, "pop": 1_800_000,
        "tempmin": 18.0, "tempmed": 22.0, "tempmax": 27.0,
        "umidmin": 50.0, "umidmed": 70.0, "umidmax": 90.0,
    }
    linha.update(sobrescritas)
    return pd.DataFrame([linha])


def test_fato_dengue_separa_ano_e_semana():
    fato = transformar_fato_dengue(bronze_dengue())
    assert (fato.loc[0, "ano"], fato.loc[0, "semana"]) == (2025, 52)
    assert pd.api.types.is_datetime64_any_dtype(fato["data_inicio_semana"])


def test_fato_dengue_uma_linha_por_municipio_semana():
    fato = transformar_fato_dengue(pd.concat([bronze_dengue(), bronze_dengue()]))
    assert len(fato) == 1


def test_fato_dengue_aceita_clima_faltando():
    # Semana sem estação meteorológica é normal e não pode quebrar o pipeline.
    fato = transformar_fato_dengue(bronze_dengue(tempmed=None))
    assert len(fato) == 1


def test_fato_dengue_barra_casos_negativos():
    with pytest.raises(AssertionError, match="negativos"):
        transformar_fato_dengue(bronze_dengue(casos=-1))


def bronze_solar(potencias, tipos=None):
    n = len(potencias)
    return pd.DataFrame({
        "codempreendimento": [f"GD.PR.{i}" for i in range(n)],
        "codmunicipioibge": "4106902",
        "dthatualizacadastralempreend": "2024-03-15",
        "dscclasseconsumo": "Residencial",
        "sigtipoconsumidor": "PF",
        "dscporte": "Microgeracao",
        "mdapotenciainstaladakw": potencias,
        "qtducrecebecredito": "1",
        "sigtipogeracao": tipos or ["UFV"] * n,
    })


def test_fato_solar_converte_decimal_brasileiro():
    # ",48" (sem o zero na frente) apareceu de verdade no arquivo da ANEEL.
    fato = transformar_fato_solar(bronze_solar(["32,50", ",48"]))
    assert fato["potencia_kw"].tolist() == [32.5, 0.48]


def test_fato_solar_remove_potencia_zero():
    fato = transformar_fato_solar(bronze_solar(["5,00", ",00"]))
    assert fato["potencia_kw"].tolist() == [5.0]


def test_fato_solar_so_fotovoltaica():
    fato = transformar_fato_solar(bronze_solar(["5,00", "100,00"], tipos=["UFV", "UTE"]))
    assert len(fato) == 1
