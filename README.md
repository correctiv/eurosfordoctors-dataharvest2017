# Run your own Euros for Doctors

This repo is for the workshop on Euros for Doctors at DataHarvest/EIJC 2017.
It uses Poland as an example country but with only two companies.

## Install

Have Python 3.5+ and install requirements:

    pip install -r requirements.txt

## Usage

- Download originals (likely PDF)
- [Setup some tables to track all companies and their data](https://docs.google.com/spreadsheets/d/1fez19N6fzL8SsSSkcthMJOrsaW5DzM2xAJrVXPLaJEo/edit#gid=1262068430)
- Convert to proper tables, [use this schema](https://docs.google.com/spreadsheets/d/1fez19N6fzL8SsSSkcthMJOrsaW5DzM2xAJrVXPLaJEo/edit#gid=0)
- Fix table structure
- Place CSVs in `data/pl/raw_csv`
- Run `01_load_data.ipynb` to do all of the following:
  - Clean and standardise data:
    - clean names: order, extract title, split name, etc.
    - clean addresses
    - clean money
  - Review samples, repeat cleaning
  - Geocode
  - Deduplicate
  - Combine entities
- Run `02_check_data.ipynb` to do some more checking
- Run `03_analysis.ipynb` to get some analysis on your data
