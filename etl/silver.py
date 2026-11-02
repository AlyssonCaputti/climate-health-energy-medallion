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
    construir_dim_municipio(engine)