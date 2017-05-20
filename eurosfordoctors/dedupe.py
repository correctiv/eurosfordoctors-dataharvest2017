import difflib
import math

import pandas as pd

from fuzzywuzzy import fuzz


def fuzzy_compare(a, b, threshold=0.9):
    if pd.isnull(a) or pd.isnull(b):
        return False
    ratio = fuzz.token_set_ratio(a, b) / 100.0
    sm = difflib.SequenceMatcher(None, a, b)
    return sm.ratio() >= threshold or ratio >= threshold


def one_contains_other(a, b):
    if pd.isnull(a) or pd.isnull(b):
        return False
    a = a.lower()
    b = b.lower()
    return a in b or b in a


def compare_rows(a, b, geoident=False, normalize=None):
    if a['type'] != b['type']:
        return False
    if a['company'] == b['company']:
        # If they got money from the same company, they are different people
        return False

    if a['type'] == 'hcp':
        threshold = 0.9
        name_match = one_contains_other(a['last_name'], b['last_name']) or fuzzy_compare(a['last_name'], b['last_name'], threshold=threshold)
        name_match = name_match and (one_contains_other(a['first_name'], b['first_name']) or fuzzy_compare(a['first_name'], b['first_name'], threshold=threshold))
    else:
        threshold = 0.93
        an, bn = a['name'], b['name']
        if pd.notnull(a['recipient_detail']):
            an += ' %s' % a['recipient_detail']
        if pd.notnull(b['recipient_detail']):
            bn += ' %s' % b['recipient_detail']
        if normalize is not None:
            an, bn = normalize(an), normalize(bn)
        name_match = one_contains_other(an, bn) or fuzzy_compare(an, bn, threshold=threshold)

    if not name_match:
        return False

    address_match = one_contains_other(a['address'], b['address']) or fuzzy_compare(a['address'], b['address'])
    location_match = one_contains_other(a['location'], b['location']) or fuzzy_compare(a['location'], b['location'])
    has_location = pd.notnull(a['location']) and pd.notnull(b['location']) and a['location'] and b['location']

    if address_match and (geoident or location_match or (not has_location and (a['type'] == 'hcp' and a['name'] == b['name']))):
        return True

    return False


def get_distance_in_km(lat1, lng1, lat2, lng2):
    R = 6371
    DegToRadFactor = math.pi / 180
    try:
        return math.acos(math.sin(lat1 * DegToRadFactor) * math.sin(lat2 * DegToRadFactor) +
            math.cos(lat1 * DegToRadFactor) * math.cos(lat2 * DegToRadFactor) *
            math.cos((lng2 - lng1) * DegToRadFactor)) * R
    except ValueError:
        return 10000  # high value


def compare_geocoded_rows(a, b, normalize=None):
    if a['type'] != b['type']:
        return False
    if pd.isnull(a['lat']):
        return False
    dist = get_distance_in_km(a['lat'], a['lng'], b['lat'], b['lng'])
    if dist > 0.5:
        return False

    return compare_rows(a, b, geoident=True, normalize=normalize)
