import json
import re

import pandas as pd
import pyprind
from slugify import slugify

from .utils import AMOUNT_FIELDS

LABEL_FIELDS = ['company', 'currency', 'type', 'year', 'recipient_detail']
PAYMENT_FIELDS = LABEL_FIELDS + AMOUNT_FIELDS

NON_WORD = re.compile('\W')


def get_usefulness(val):
    # Crude entropy estimation
    if pd.isnull(val):
        return 0.0
    return len(val) / float(len(NON_WORD.split(val)))


def get_best_value(series):
    vc = series.value_counts()
    if len(vc) == 0:
        lvi = series.last_valid_index()
        if lvi is None:
            return None
        return series[lvi]
    if len(vc) == 1:
        return vc.idxmax()
    if vc.name not in ('location', 'address', 'name', 'first_name', 'last_name'):
        return vc.idxmax()
    vc = vc.rank(method='dense', ascending=False)
    candidates = list(vc[vc == 1.0].index)
    candidates = [(get_usefulness(c), c) for c in candidates]
    candidates = sorted(candidates, key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def make_entities(df):
    columns = set(list(df.columns)) - {'uid'}
    columns = columns - set(PAYMENT_FIELDS) | {'type'}

    groups = df.groupby('uid')
    progress_logger = pyprind.ProgPercent(len(groups))

    for index, rows in groups:
        entity = {
            k: get_best_value(rows[k]) for k in columns
        }
        melted_rows = pd.melt(rows[PAYMENT_FIELDS], id_vars=LABEL_FIELDS,
                              value_vars=AMOUNT_FIELDS, var_name='label', value_name='amount')
        entity['payments'] = json.dumps([row.to_dict() for i, row in melted_rows.iterrows()
                                             if pd.notnull(row['amount']) and row['amount'] > 0])
        yield entity
        progress_logger.update()


def make_entities_df(df):
    return pd.DataFrame(make_entities(df), dtype="object")


def make_slug(x):
    slug_list = [slugify(x['name'] or ''), slugify(x['location'] or '')]
    origin = x['origin'].lower()
    if origin != 'de':
        slug_list.append(origin)
    slug_list = [s for s in slug_list if s]
    return '-'.join(slug_list)


def make_slugs(df):

    df['slug_raw'] = df.apply(make_slug, 1)

    df['slug'] = df['slug_raw'].copy()
    groups = df.groupby('slug_raw')
    for key, group_df in groups:
        if len(group_df) < 2:
            continue
        for i, (index, row) in enumerate(group_df.iterrows()):
            if i == 0:
                continue
            df.set_value(index, 'slug', '%s-%s' % (row['slug_raw'], i))
    return df
