#!/usr/bin/env python3
"""Build trackers/ggit-goget/goget_map_latest.geojson for the combined map.

The file lives under trackers/ because that's the only place .gitignore lets
geojson be committed. Downloads the data team's GOGET map export from the
public CDN and renames its
properties to the handoff-schema names the pipeline maps already use
(PipelineName, Status, Wiki, ...), so one tracker config can drive pipelines
(lines) and extraction areas (points) together.

Source: the newest goget_map_*.geojson under
https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/
(update SOURCE_URL when the data team publishes a new one, then rerun):

    python3 scripts/build_goget_map_data.py

Commit and push the regenerated goget_map_latest.geojson; the ggit-goget map
loads it from this repo's raw.githubusercontent.com URL.
"""

import json
import urllib.request
from pathlib import Path

SOURCE_URL = 'https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/goget_map_2026-03.geojson'
OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget' / 'goget_map_latest.geojson'

# million boe/y -> boe/d, so CapacityBOEd means the same thing it does on the
# pipeline features (circle scaling only compares points to points, but keep
# the field honest)
MILLION_BOE_Y_TO_BOE_D = 1e6 / 365.0


def clean_year(value):
    """Years arrive as '1954', 2022.0, or '' — normalize to int-ish strings."""
    if value in (None, ''):
        return ''
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def transform(props):
    capacity_scaled = props.get('capacity-scaled')
    if isinstance(capacity_scaled, (int, float)):
        capacity_boed = round(capacity_scaled * MILLION_BOE_Y_TO_BOE_D, 1)
    else:
        capacity_boed = ''

    return {
        'PipelineName': props.get('name', ''),
        'SegmentName': '',  # keeps the shared hover popup from printing undefined
        'Status': props.get('status', ''),
        'Wiki': props.get('url', ''),
        'ProjectID': props.get('project-id', ''),
        'CountriesOrAreas': props.get('all-countries') or props.get('country-area1', ''),
        'StartState/Province': props.get('subnational', ''),
        'StartLocation': props.get('location-display', ''),
        'Owner': props.get('owner', ''),
        'Parent': props.get('parent', ''),
        'Operator': props.get('operator', ''),
        'StartYear1': clean_year(props.get('start-year')),
        'DiscoveryYear': clean_year(props.get('discovery-year')),
        'FIDYear': clean_year(props.get('fid-year')),
        'ProdOil': props.get('prod-oil', ''),
        'ProdOilYear': clean_year(props.get('prod-year-oil')),
        'ProdGas': props.get('prod-gas', ''),
        'ProdGasYear': clean_year(props.get('prod-year-gas')),
        'LocationAccuracy': props.get('location-accuracy', ''),
        'Capacity': props.get('capacity-display', ''),
        'CapacityUnits': props.get('units-of-m', ''),
        'CapacityBOEd': capacity_boed,
        'Tracker': 'GOGET',
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
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f'wrote {OUT_PATH.name}: {len(features)} features, {size_mb:.1f} MB')


if __name__ == '__main__':
    main()
