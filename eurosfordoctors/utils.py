import json

import pandas as pd
import pyprind


def progress_pandas_df():
    def inner(df, func, *args, **kwargs):
        df_len = len(df) + 1
        progress_logger = pyprind.ProgPercent(df_len)

        def wrapper(*args, **kwargs):
            try:
                progress_logger.update()
            except ValueError:
                pass
            return func(*args, **kwargs)
        result = df.apply(wrapper, *args, **kwargs)
        return result
    pd.DataFrame.progress_apply = inner
    pd.Series.progress_apply = inner


MONEY_FIELDS = 'donations_grants	sponsorship	registration_fees	travel_accommodation	fees	related_expenses	total'.split()
MONEY_FIELDS_ONLY = list(set(MONEY_FIELDS) - {'total'})
AMOUNT_FIELDS = MONEY_FIELDS_ONLY
MONEY_FIELDS_ALL = MONEY_FIELDS_ONLY + ['computed_total']
TRANSLATE = {
    'fees': 'Honorare',
    'related_expenses': 'Spesen',
    'travel_accommodation': 'Reisekosten',
    'registration_fees': 'Tagungsgebühren',
    'donations_grants': 'Spenden/Zuwendungen',
    'sponsorship': 'Sponsoring',
    'computed_total': 'Gesamtbetrag',
}

MONEY_FIELDS_ALL_TRANSLATED = [TRANSLATE.get(k, k) for k in MONEY_FIELDS_ALL]


def unpack_json(row):
    df = pd.DataFrame(json.loads(row['payments']))
    if 'amount' not in df:
        return row
    row['computed_total'] = df['amount'].sum()
    for f in MONEY_FIELDS_ONLY:
        row[f] = df[df['label'] == f]['amount'].sum()
    return row


def company_sample(df, count=3):
    companies = list(df['company'].value_counts().index)
    gen = (df[df['company'] == c] for c in companies)
    gen = ((x, len(x)) for x in gen if len(x) > 0)
    l = list(x.sample(count if l >= count else l) for x, l in gen)
    if l:
        return pd.concat(l)
    return df[df['name'].isnull()]
