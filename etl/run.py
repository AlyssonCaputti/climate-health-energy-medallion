"""Orquestrador: roda bronze → silver → gold → ml na ordem certa.

python run.py                → pipeline inteiro
python run.py silver gold    → só as camadas que eu pedir
"""

import sys
import time

import bronze
import gold
import ml
import silver
from db import get_engine

# A ordem aqui é o contrato do pipeline: cada camada só lê da anterior.
CAMADAS = {
    "bronze": bronze.FONTES,
    "silver": silver.ETAPAS,
    "gold": gold.ETAPAS,
    "ml": ml.MODELOS,
}


def main(camadas):
    engine = get_engine()
    inicio = time.perf_counter()
    for camada in camadas:
        for nome, etapa in CAMADAS[camada].items():
            t = time.perf_counter()
            print(f"▶ {camada}.{nome}")
            etapa(engine)
            print(f"  ok em {time.perf_counter() - t:.1f}s")
    print(f"✔ pipeline concluído em {time.perf_counter() - inicio:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:] or list(CAMADAS))
