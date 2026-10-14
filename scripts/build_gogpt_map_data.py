#!/usr/bin/env python3
"""Build trackers/ggit-goget-gogpt/gogpt_map_latest.geojson — GOGPT units.

Reads the oil & gas power plant units straight from the GEM project database
and writes one point per generating unit with the handoff-schema property
names the pipeline maps already use (PipelineName, Status, Wiki, ...), so one
tracker config can drive pipelines (lines), extraction areas (polygons +
points) and power plants (points) together. Until October 2026 this
converted the data team's GOGPT map export from the public CDN instead; the
database is fresher and rebuilds on every workflow run.

The rows come from gem-db-ops' `export_gogpt_all_fields` (the same code that
produces the GOGPT all-fields spreadsheet, so owners, parents, status and
technology are spelled the way the published data spells them), written to a
temporary CSV and reduced to the columns the map needs. Units are kept when
`powerplant_unit.trackerSearch` is 'GOGPT' and they have coordinates and a
status; the few that lack either are counted in the build log.

Needs GEM_READONLY_DB_URL in the environment (read-only Postgres role) and the
sibling gem-db-ops checkout (see scripts/gem_db.py):

    python3 scripts/build_gogpt_map_data.py

Features stay UNIT-level, one per generating unit. The shell groups features
that share linkField + coordinates, so a station's units collapse into a
single map circle (a pie chart when its units have different statuses) while
the detail card still lists them individually.

This script is independent of the two GOGET builders — plants and extraction
areas are separate assets, so there is no de-duplication step between them and
no required run order.

Commit and push the regenerated gogpt_map_latest.geojson; the ggit-goget-gogpt
map loads it from this repo's raw.githubusercontent.com URL.
"""

import csv
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gem_db  # read-only GEM connection, borrowed from the sibling gem-db-ops repo

OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget-gogpt' / 'gogpt_map_latest.geojson'

GOGPT_TRACKER = 'GOGPT'

# ~0.1 m at the equator; the export carries seven decimals.
COORD_PRECISION = 6

# Display-only multiplier written to CapacityMapScale, the field the shell sizes
# circles by. Plant capacity is nameplate MW; pipeline and extraction capacity is
# boe/d, two or three orders of magnitude larger, so raw MW would pin every plant
# at the minimum radius with no visible difference between a 30 MW genset and a
# 6 GW station. 100 puts the largest units in the same visual range as a large gas
# field without asserting any equivalence between the two: no efficiency, heat
# rate or utilization assumption is implied, and the honest numbers stay in
# Capacity/CapacityUnits ('6000', 'MW'), which is what the map and the downloads
# report.
MW_TO_MAP_SCALE = 100


def clean_year(value):
    """Years arrive as '1954', 2022.0, or '' — normalize to int-ish strings."""
    if value in (None, ''):
        return ''
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def clean_status(value):
    """'shelved - inferred 2 y' → 'shelved': the map's status vocabulary has no inferred variants."""
    return (value or '').split(' - ')[0].strip()


def clean_capacity(value):
    """'6000.0' → '6000', '5.5' stays; the display string the table shows."""
    if value in (None, ''):
        return ''
    try:
        number = float(value)
    except ValueError:
        return str(value)
    return f'{number:.3f}'.rstrip('0').rstrip('.')


def transform(row):
    capacity = clean_capacity(row.get('Capacity (MW)'))
    map_scale = round(float(capacity) * MW_TO_MAP_SCALE, 1) if capacity else ''
    unit_name = (row.get('Unit name') or '').strip()
    if unit_name.lower().startswith('unit'):
        unit_name = unit_name[4:].strip()  # 'Unit 3-b' is already a unit label
    subnational = (row.get('State/Province') or '').strip()
    country = (row.get('Country/Area') or '').strip()
    return {
        'PipelineName': row.get('Plant name', ''),
        # the hover popup's gray subheading and the detail card's unit line
        'SegmentName': f'Unit {unit_name}' if unit_name else '',
        'Status': clean_status(row.get('Status')),
        'Wiki': row.get('Wiki URL', ''),
        'ProjectID': row.get('GEM location ID', ''),
        'UnitID': row.get('GEM unit ID', ''),
        'CountriesOrAreas': country,
        'StartState/Province': subnational,
        'StartLocation': ', '.join(p for p in (subnational, country) if p),
        'Owner': row.get('Owner(s)', ''),
        'Parent': row.get('Parent(s)', ''),
        'Operator': row.get('Operator(s)', ''),
        'StartYear1': clean_year(row.get('Start year')),
        'LocationAccuracy': row.get('Location accuracy', ''),
        'FuelType': row.get('Fuel', ''),
        'TechType': row.get('Turbine/Engine Technology', ''),
        'Capacity': capacity,
        'CapacityUnits': 'MW',
        'CapacityMapScale': map_scale,
        'Tracker': GOGPT_TRACKER,
    }


def gogpt_unit_ids():
    """'G' + id of every unit the GOGPT tracker owns (combustion units also cover coal and bioenergy)."""
    rows = gem_db.fetch_all(
        'select id from powerplant_unit where "trackerSearch" = :tracker and deleted is not true',
        {'tracker': GOGPT_TRACKER},
    )
    return {f'G{row[0]}' for row in rows}


def export_rows():
    """Every combustion unit row of the all-fields export, via gem-db-ops."""
    sys.path.insert(0, str(gem_db.db_ops_repo()))
    from gem_all_fields import export_gogpt_all_fields

    engine = gem_db.build_readonly_engine()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / 'gogpt.csv'
        export_gogpt_all_fields(engine, str(csv_path))
        with csv_path.open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))


def main():
    unit_ids = gogpt_unit_ids()
    print(f'{len(unit_ids)} GOGPT units in the database')
    rows = export_rows()
    print(f'exported {len(rows)} combustion units through gem-db-ops')

    features = []
    counts = Counter()
    for row in rows:
        if row.get('GEM unit ID') not in unit_ids:
            counts['not GOGPT'] += 1
            continue
        if not row.get('Latitude') or not row.get('Longitude'):
            counts['no coordinates'] += 1
            continue
        if not clean_status(row.get('Status')):
            counts['no status'] += 1  # the map's filter has nowhere to put it
            continue
        geometry = {'type': 'Point', 'coordinates': [round(float(row['Longitude']), COORD_PRECISION),
                                                      round(float(row['Latitude']), COORD_PRECISION)]}
        features.append({'type': 'Feature', 'geometry': geometry, 'properties': transform(row)})

    out = {'type': 'FeatureCollection', 'features': features}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))
    size_mb = OUT_PATH.stat().st_size / 1e6
    stations = len({f['properties']['ProjectID'] for f in features})
    print(f'wrote {OUT_PATH.name}: {len(features)} units at {stations} stations, {size_mb:.1f} MB')
    print('left out: ' + ', '.join(f'{v} {k}' for k, v in counts.items()))
    print('statuses: ' + ', '.join(f'{k} {v}' for k, v in Counter(f['properties']['Status'] for f in features).most_common()))


if __name__ == '__main__':
    main()
