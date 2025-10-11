import numpy as np
import pandas as pd


def mad_outliers(df:pd.DataFrame, col="close", z=3.5):
    x = df[col].astype(float)
    med = np.median(x)
    mad = np.median(np.abs(x - med)) or 1e-12
    mod_z = 0.6745 * (x - med) / mad
    df = df.copy()
    df["anomaly"] = np.abs(mod_z) > z
    df["mod_z"] = mod_z
    return df