import os
import json

import pandas as pd
import geocoder
import dataset


DIR_PATH = os.path.abspath(os.path.dirname(__file__))
API_KEY = open(os.path.join(DIR_PATH, 'apikey.txt')).read().strip()

db = dataset.connect('sqlite:///geocoding.db')


def get_search(row):
    search = ', '.join(x for x in (row['address'], row['location']) if pd.notnull(x) and x)
    return search.strip()


def geocode(row, country='de'):
    table = db['geocoding']
    kwargs = {'key': API_KEY, 'language': country}
    if pd.notnull(row['country']):
        kwargs.update({'components': 'country:%s' % row['country']})
        country = row['country']
    search = get_search(row)

    result = table.find_one(country=country, location=search)
    if result is None:
        geocoding_result = geocoder.google(search, **kwargs)
        latlng = [None, None]
        if geocoding_result.geojson['properties']['status'] == "OVER_QUERY_LIMIT":
            raise Exception('Over query API limit')
        if geocoding_result and geocoding_result.latlng:
            latlng = geocoding_result.latlng
        table.insert(dict(country=country, location=search,
                          lat=latlng[0], lng=latlng[1],
                          geojson=json.dumps(geocoding_result.geojson)))
        return latlng
    return (result['lat'], result['lng'])


def run_geocoding(row, country='de'):
    row['lat'], row['lng'] = geocode(row, country=country)
    return row


def get_postcode(row):
    if pd.notnull(row['postcode']):
        return row['postcode']
    table = db['geocoding']
    country = ''
    if pd.notnull(row['country']):
        country = row['country']
    search = get_search(row)

    result = table.find_one(country=country, location=search)
    if result is None:
        return None
    data = json.loads(result['geojson'])
    return data['properties'].get('postal')
