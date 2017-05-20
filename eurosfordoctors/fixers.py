import re
from collections import Counter

import numpy as np
import pandas as pd

from slugify import slugify


MONEY_FIELDS = 'donations_grants	sponsorship	registration_fees	travel_accommodation	fees	related_expenses	total'.split()
CURRENCY_RE = re.compile('EUR|Euro|€|CHF', re.I)
DECIMAL_RE = re.compile('.*([\.,])\d{1,2}$')
POSTCODE = re.compile('\d{4,5}')
POSTCODE_CITY = re.compile('(.*?),?\s*(\d{4,5})\s*(\w+)')
ADDRESS_CITY = re.compile('(.*\d[a-z]?),\s(.+)')
NORMALIZE_STREET = re.compile('([Ss])(trasse|traße)($|\W)', re.U | re.I)
MULTI_SPACE = re.compile('\s+')
MALE_GENDER = re.compile('^(Herrn?|Mr\.|Monsieur)\s+', re.I)
FEMALE_GENDER = re.compile('^(Frau|Mrs\.|Signora)\s+', re.I)
CLEAN_NAME = re.compile('^([\w\-]{2,})(?:\s+[A-Z]\.?)*\s([\w\-]{2,})')
PUNCTUATION = re.compile('^(.*)[\W\D]?$')
NAME_DASH_SPACE = re.compile('[a-z]\-(\s+)')
ENDS_DASH = re.compile('\s+-(\s*)$')
WEIRD_SPACE = re.compile('([a-zßöüä]+)(\s)([a-zßöüä]{1,3}\.?)(\W|$)')
HCO_SUB_NAME_SPLITTER = re.compile('\s-\s?|\s\|\s|,\s|\s\(')
BAD_RECIPIENT_DETAIL = re.compile('g?GmbH|GbR', re.I | re.U)
BAD_HOUSE_NUMBER = re.compile('(\D)(\d{2})(\d{2})$')
ORGANISED_BY = re.compile('^(organi?siert|org\. )?(durch|von)?:?\s?', re.I)
WORDS_ONLY = re.compile('^\w+$')
NO_WORDS = re.compile('\W')

REPLACEMENTS = {
    'e. V.': 'e.V.'
}

RE_NAME_FIXES = {
    '0A': 'OA',
    '([a-z])\-\s+([A-Z])': '\\1-\\2',
    ' ße ': 'ße ',
    ';\s*$': '',
    '\.(\d)': '. \\1',
    r'^[\W_]*(.*?)[\W_]*$': '\\1',
    '\s': ' ',
    '\.\.\.': '',
}

RE_REPLACEMENTS = {
    '(\S)e\.V\.': '\\1 e.V.'
}


def rec(x, *args):
    return re.compile(x, *args)

TITLES = (
    rec(u'Dipl?\.\-?[\w\.-]+(?:\s?\(FH\))?', re.I),
    rec('(?:PD|MD|OA)\s'),
    rec('[A-Z][a-z]{1,4}(?:[A-Z][a-z]{,4})+'),
    rec(r'^(?:(?:Docteur|Dottoressa|Professor|Professeur|Egregio|Chairman|Chairwoman|Dott|Dr|Prof|Univ|Prim|Ass|Assoc|Priv|Doz|Mag|MBA|MSc|stom|nat|dent|univers|habil|med|dipl|priv|doz|oec|troph|lic|phil|pract)\.?[-‐\s]*)+(?![a-z])', re.I),
    rec('(?:Prof\.)?(?:\s?Dr\.(?:\s?h\.c\.)?(?:\s?[a-z]+\.)?)*(?:-Ing\.)?', re.I),
    rec('(?:Chef)?[Aa]potheker(?:in)?', re.I),
)

weirdspace_counter = Counter()


def weirdspace_replace(matchobj):
    if matchobj.group(3) not in ('von', 'van', 'für', 'der', 'die', 'das', 'am',
                                 'und', 'im', 'des', 'an', 'in', 'dem', 'zur', 'dem', 'mit'):
        weirdspace_counter[matchobj.group(3)] += 1
        return '%s%s%s' % (matchobj.group(1), matchobj.group(3), matchobj.group(4))
    return '%s%s%s%s' % matchobj.groups()


def pdf_space_fixer(val):
    # Breaks more things than it fixes
    return val
    # return WEIRD_SPACE.sub(weirdspace_replace, val)


def apply_name_fixes(val, fixes=RE_NAME_FIXES):
    for k, v in fixes.items():
        val = re.sub(k, v, val)
    return val


def replace_words(val):
    for k, v in REPLACEMENTS.items():
        val = val.replace(k, v)
    for k, v in RE_REPLACEMENTS.items():
        val = re.sub(k, v, val)
    return val


def get_titles(name):
    titles = []
    new_name = name
    for title in TITLES:
        matches = title.findall(new_name)
        for match in matches:
            if not match.strip():
                continue
            try:
                index = new_name.index(match)
            except ValueError:
                print(name, new_name, match)
                raise
            new_name = new_name.replace(match, '', 1)
            new_name = new_name.strip()
            titles.append((index, match.strip()))
    if titles:
        titles.sort(key=lambda x: x[0])
        titles = ' '.join([x[1] for x in titles])
        titles = titles.replace('/ ', '/')
    else:
        titles = None
    if not new_name:
        new_name = name.strip()
    return titles, new_name


def split_hco_name(row, COMPANY_SETTINGS):
    split_name = HCO_SUB_NAME_SPLITTER.split(row['name'], 1)
    if len(split_name) > 1:
        success = True
        name, detail = split_name
        if name.endswith('-'):
            success = False
        detail = detail.strip()
        if detail.endswith(')'):
            detail = detail.replace(')', '')
        match = ORGANISED_BY.search(detail)
        if match and len(match.group(0)) > 4:
            # Switch around
            detail = ORGANISED_BY.sub('', detail)
            name, detail = detail, name

        match = ORGANISED_BY.search(name)
        if match and len(match.group(0)) > 4:
            name = ORGANISED_BY.sub('', name)

        if len(name) < 5 or (is_upper(NO_WORDS.sub('', name)) and len(name) < 6):
            success = False
        if detail.strip().startswith('und'):
            success = False
        if success:
            row['name'] = name
            row['recipient_detail'] = detail
    # row['name'] = NAME_DASH_SPACE.sub('', row['name'])
    row['name'] = ENDS_DASH.sub('', row['name']).strip()
    if row['company'] not in COMPANY_SETTINGS['no_pdf']:
        row['name'] = pdf_space_fixer(row['name'])
    row['name'] = replace_words(row['name'])
    return row


def split_name(row, COMPANY_SETTINGS):
    if row['type'] == 'hco':
        return split_hco_name(row, COMPANY_SETTINGS)
    if 'first_name' in row and row['first_name']:
        return row

    name = row['name']
    if ',' in name:
        parts = name.split(',')
        name_list = list(reversed(parts))
    else:
        if row['company'] in COMPANY_SETTINGS['bad_name_order']:
            if row['company'] in COMPANY_SETTINGS.get('last_name_capitals', []):
                name_list = re.match('^([^a-z]+) ((?:[A-ZÖÜÄ][^A-Z]+)+)$', name)
                if name_list is None:
                    print(name, row['company'], row)
                name_list = [name_list.group(1), name_list.group(2)]
            else:
                name_list = name.split(' ', 1)
        else:
            name_list = name.rsplit(' ', 1)

    if row['company'] in COMPANY_SETTINGS['bad_name_order']:
        name_list = reversed(name_list)

    name_list = [MULTI_SPACE.sub(' ', x) for x in name_list]
    name_list = [n.title() if is_upper(n) else n for n in name_list]
    row['name'] = ' '.join(name_list).strip()
    row['first_name'] = ' '.join(name_list[:-1]).strip()
    row['last_name'] = name_list[-1].strip()
    row['name'] = ' '.join(name_list).strip()

    for k in ('name', 'first_name', 'last_name'):
        row[k] = NAME_DASH_SPACE.sub('', row[k])
        if row['company'] not in COMPANY_SETTINGS['no_pdf']:
            row[k] = pdf_space_fixer(row[k])

    row['name'] = MULTI_SPACE.sub(' ', row['name'])
    row['clean_name'] = slugify(CLEAN_NAME.sub('\\1 \\2', row['name']).lower())
    return row


def is_upper(val):
    val = val.replace('ß', '').replace('ü', '').replace('ä', '').replace('ö', '')
    return val.upper() == val


def fix_name(row, COMPANY_SETTINGS):
    row['name'] = apply_name_fixes(row['name'])

    if row['type'] == 'hcp':
        match_m = MALE_GENDER.search(row['name'])
        match_f = FEMALE_GENDER.search(row['name'])
        if match_m is not None:
            row['name'] = MALE_GENDER.sub('', row['name']).strip()
            row['gender'] = 'Herr'
        if match_f is not None:
            row['name'] = FEMALE_GENDER.sub('', row['name']).strip()
            row['gender'] = 'Frau'
        if row['company'] in COMPANY_SETTINGS.get('semicolon_name_split', []):
            row['name'] = ' '.join(row['name'].split(';'))
        if row['company'] in COMPANY_SETTINGS.get('comma_split_title', []):
            if ',' in row['name']:
                row['name'], row['title'] = row['name'].split(',', 1)
        elif row['company'] in COMPANY_SETTINGS.get('comma_split_title_name', []):
            name = row['name'].split(',', 2)
            if len(name) == 3:
                row['title'] = name[1]
                row['name'] = ', '.join(name[:1] + name[2:])
            else:
                row['name'] = ', '.join(name)
        else:
            title, name = get_titles(row['name'])
            row['title'] = title
            row['name'] = name

    if is_upper(row['name']) and len(row['name']) > 4:
        row['name'] = row['name'].title()

    return row


def extract_location(row, COMPANY_SETTINGS):
    if row['company'] not in COMPANY_SETTINGS['no_pdf']:
        row['location'] = pdf_space_fixer(row['location'])
    if is_upper(row['location']):
        row['location'] = row['location'].title()
    if row['company'] not in COMPANY_SETTINGS['no_postcode']:
        match = POSTCODE.search(row['location'])
        if match is not None:
            postcode = match.group(0)
            row['location'] = row['location'].replace(postcode, '').strip()
            row['postcode'] = postcode
    row['location'] = apply_name_fixes(row['location'])
    return row


def fix_address(row, COMPANY_SETTINGS):
    if pd.notnull(row['location']):
        row = extract_location(row, COMPANY_SETTINGS)
    if pd.notnull(row['address']):
        if is_upper(row['address']):
            row['address'] = row['address'].title()
        if row['company'] not in COMPANY_SETTINGS['no_pdf']:
            row['address'] = pdf_space_fixer(row['address'])

        row['address'] = NORMALIZE_STREET.sub('\\1tr.\\3', row['address'])

        if row['company'] in COMPANY_SETTINGS['hcp_company_in_address']:
            parts = row['address'].rsplit(', ', 2)
            if len(parts) == 3:
                row['address'] = ', '.join(parts[1:])
                if row['recipient_detail']:
                    row['recipient_detail'] += ', ' + parts[0]
                else:
                    row['recipient_detail'] = parts[0]

        if row['company'] in COMPANY_SETTINGS.get('address_rules', []):
            try:
                matches = COMPANY_SETTINGS['address_rules'][row['company']](row['address'])
            except Exception:
                print(row['address'])
                raise
            for k in matches:
                row[k] = matches[k]

        if row['company'] not in COMPANY_SETTINGS['no_postcode']:
            match = POSTCODE_CITY.match(row['address'])
            if match is not None:
                row['address'] = match.group(1)
                row['postcode'] = match.group(2)
            else:
                match = POSTCODE.search(row['address'])
                if match is not None:
                    postcode = match.group(0)
                    row['address'] = row['address'].replace(postcode, '').strip()
                    row['postcode'] = postcode
        if pd.isnull(row['location']):
            match = ADDRESS_CITY.match(row['address'])
            if match is not None:
                row['address'] = match.group(1).strip()
                row['location'] = match.group(2).strip()
        else:
            row = extract_location(row, COMPANY_SETTINGS)

        row['address'] = PUNCTUATION.sub('\\1', row['address'])
        row['address'] = apply_name_fixes(row['address'])
        match = BAD_HOUSE_NUMBER.search(row['address'])
        if match is not None:
            n1, n2 = int(match.group(2)), int(match.group(3))
            if abs(n1 - n2) < 5:
                row['address'] = BAD_HOUSE_NUMBER.sub('%s%s-%s' % (match.group(1), n1, n2), row['address'])
    if pd.notnull(row['location']):
        row['location'] = apply_name_fixes(row['location'])
    return row


def fix_money(val):
    if not isinstance(val, str):
        return val
    if val == '-':
        return None

    val = val.replace("'", '')  # Swiss thousand separator

    if val == 'N/A' or val == 'NA':
        return None

    val = CURRENCY_RE.sub('', val).strip()
    val = val.replace(' ', '')

    match = DECIMAL_RE.match(val)
    if match is not None:
        if match.group(1) == ',':
            val = val.replace('.', '').replace(',', '.')
        else:
            val = val.replace(',', '')
    if ',' in val:
        val = val.replace(',', '')
    return val


def make_money(df):
    for field in MONEY_FIELDS:
        if field not in df:
            continue
        df[field + '_dirty'] = df[field]
        df[field] = df[field].apply(fix_money)
        try:
            df[field] = pd.to_numeric(df[field])
            df[field] = df[field].apply(lambda x: np.nan if x <= 0 else x)
        except ValueError as e:
            print(field)
            raise e
    return df


def fix_country(val, default='DE'):
    if pd.isnull(val):
        return default
    val = val.lower()
    if 'germany' in val or 'deutschland' in val or val == 'de':
        return 'DE'
    if 'austria' in val or 'sterreich' in val or val == 'at':
        return 'AT'
    if 'niederlande' in val:
        return 'NL'
    if 'schweiz' in val or 'switzerland' in val:
        return 'CH'
    if 'kroatien' in val:
        return 'HR'
    if 'france' in val:
        return 'FR'
    if 'USA' in val:
        return 'US'
    return val.upper()
