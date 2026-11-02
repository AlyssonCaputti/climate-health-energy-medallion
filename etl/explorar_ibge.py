"""Rascunho de exploração: o primeiro olhar que dei na API do IBGE antes de modelar qualquer coisa.

Deixo aqui de propósito. Foi rodando isso que achei o município sem microrregião.
"""

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

# Meu checklist de toda fonte nova: formato, colunas, tipos e nulos.
df = pd.json_normalize(dados)
print("\nFormato:", df.shape)
print("\nColunas:")
print(df.columns.tolist())
print("\nTipos:")
print(df.dtypes)
print("\nNulos por coluna:")
print(df.isna().sum())
