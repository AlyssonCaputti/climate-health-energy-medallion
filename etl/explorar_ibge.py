import pandas as pd
import requests

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

resposta = requests.get(URL, timeout=60)
print("Status:", resposta.status_code)

resposta.raise_for_status()
dados = resposta.json()

print("Tipo:", type(dados))
print("Quantidade:", len(dados))
print("Primeiro item:", dados[0])

df = pd.json_normalize(dados)
print("\nFormato:", df.shape)
print("\nColunas:")
print(df.columns.tolist())
print("\nTipos:")
print(df.dtypes)
print("\nNulos por coluna:")
print(df.isna().sum())