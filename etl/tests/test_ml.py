import numpy as np
import pandas as pd

from ml import LAGS, ajustar_bass, base_polinomial, bass


def test_bass_recupera_parametros_conhecidos():
    # Gero uma curva com parâmetros que eu conheço e vejo se o ajuste chega perto deles.
    t = np.arange(150)
    y = bass(t, m=1000, p=0.002, q=0.08)

    m, p, q = ajustar_bass(y)

    assert abs(m - 1000) / 1000 < 0.05
    assert abs(q - 0.08) < 0.01


def test_base_polinomial_com_clima_constante():
    # Se toda semana tem 20 °C, o termo de grau 0 é só 20 × 8 lags.
    df = pd.DataFrame({f"temp_med_lag{lag}": [20.0] for lag in LAGS})
    base = base_polinomial(df, "temp_med")
    assert base.loc[0, "temp_med_p0"] == 20.0 * len(LAGS)
    assert list(base.columns) == ["temp_med_p0", "temp_med_p1", "temp_med_p2"]
