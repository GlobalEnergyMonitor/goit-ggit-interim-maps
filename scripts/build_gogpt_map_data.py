#!/usr/bin/env python3
"""Build trackers/ggit-goget-gogpt/gogpt_map_latest.geojson for the combined map.

Same idea as build_goget_map_data.py: download the data team's GOGPT map export
from the public CDN and rename its properties to the handoff-schema names the
pipeline maps already use (PipelineName, Status, Wiki, ...), so one tracker
config can drive pipelines (lines), extraction areas (polygons + points) and
oil & gas power plants (points) together.

Source: the newest gogpt_map_*.geojson under
https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/
(update SOURCE_URL when the data team publishes a new one, then rerun):

    python3 scripts/build_gogpt_map_data.py

Features stay UNIT-level, one per generating unit, the way the export ships
them. The shell groups features that share linkField + coordinates, so a
station's units collapse into a single map circle (a pie chart when its units
have different statuses) while the detail card still lists them individually.

This script is independent of the two GOGET builders — plants and extraction
areas are separate assets, so there is no de-duplication step between them and
no required run order.

Commit and push the regenerated gogpt_map_latest.geojson; the ggit-goget-gogpt
map loads it from this repo's raw.githubusercontent.com URL.
"""

import json
import urllib.request
from pathlib import Path

SOURCE_URL = 'https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/gogpt_map_2026-01.geojson'
OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget-gogpt' / 'gogpt_map_latest.geojson'

# Display-only multiplier written to CapacityMapScale, the field the shell sizes
# circles by. Plant capacity is nameplate MW; pipeline and extraction capacity is
# boe/d, two or three orders of magnitude larger, so raw MW would pin every plant
# at the minimum radius with no visible difference between a 30 MW genset and a
# 6 GW station. 100 puts the largest units in the same visual range as a large gas
# field without asserting any equivalence between the two: no efficiency, heat
# rate or utilisation assumption is implied, and the honest numbers stay in
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


def transform(props):
    capacity_mw = props.get('capacity-scaled')
    if isinstance(capacity_mw, (int, float)):
        map_scale = round(capacity_mw * MW_TO_MAP_SCALE, 1)
    else:
        map_scale = ''

    unit_name = str(props.get('unit-name', '')).strip()

    return {
        'PipelineName': props.get('name', ''),
        # the hover popup's gray subheading and the detail card's unit line
        'SegmentName': f'Unit {unit_name}' if unit_name else '',
        'Status': props.get('status', ''),
        'Wiki': props.get('url', ''),
        'ProjectID': props.get('project-id', ''),
        'UnitID': props.get('unit-id', ''),
        'CountriesOrAreas': props.get('all-countries') or props.get('country-area1', ''),
        'StartState/Province': props.get('subnational', ''),
        'StartLocation': props.get('location-display', ''),
        'Owner': props.get('owner', ''),
        'Parent': props.get('parent', ''),
        'Operator': props.get('operator', ''),
        'StartYear1': clean_year(props.get('start-year')),
        'FuelType': props.get('fuel', ''),
        'TechType': props.get('tech-type', ''),
        'Capacity': props.get('capacity-display', ''),
        'CapacityUnits': props.get('units-of-m', ''),
        'CapacityMapScale': map_scale,
        'Tracker': 'GOGPT',
    }


def main():
    print(f'downloading {SOURCE_URL}')
    with urllib.request.urlopen(SOURCE_URL) as response:
        data = json.load(response)

    features = []
    for feature in data['features']:
        if not feature.get('geometry'):
            continue
        features.append({
            'type': 'Feature',
            'geometry': feature['geometry'],
            'properties': transform(feature['properties']),
        })

    out = {'type': 'FeatureCollection', 'features': features}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))
    size_mb = OUT_PATH.stat().st_size / 1e6
    stations = len({f['properties']['Wiki'] for f in features})
    print(f'wrote {OUT_PATH.name}: {len(features)} units at {stations} stations, {size_mb:.1f} MB')


if __name__ == '__main__':
    main()
