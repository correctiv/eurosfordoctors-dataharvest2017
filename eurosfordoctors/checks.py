import numpy as np

from .utils import MONEY_FIELDS_ONLY


def check_computed_total(df):
    df['computed_total'] = df[MONEY_FIELDS_ONLY].sum(1)
    view = ['company', 'index', 'name', 'address', 'total', 'total_dirty', 'computed_total'] + MONEY_FIELDS_ONLY
    return df[~np.isclose(df['computed_total'], df['total'], atol=1) & df['total'].notnull() & df['total'] != 0.0][view]
