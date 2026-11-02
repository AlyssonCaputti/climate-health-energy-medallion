from datetime import datetime, timezone

import pandas as pd
import requests

from db import get_engine

URL_IBGE_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def ingerir_ibge_municipios(engine):
    resposta = requests.get(URL_IBGE_MUNICIPIOS, timeout=60)
    resposta.raise_for_status()

    df = pd.json_normalize(resposta.json())
    df.columns = df.columns.str.replace(r"[.-]", "_", regex=True).str.lower()
    df["_fonte"] = URL_IBGE_MUNICIPIOS
    df["_ingerido_em"] = datetime.now(timezone.utc)

    df.to_sql("ibge_municipios", engine, schema="bronze", if_exists="replace", index=False)
    print(f"bronze.ibge_municipios: {len(df)} linhas")


if __name__ == "__main__":
    engine = get_engine()
    ingerir_ibge_municipios(engine)
