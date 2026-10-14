#!/usr/bin/env python3
"""Build trackers/ggit-goget/goget_map_latest.geojson — GOGET centroids.

The file lives under trackers/ because that's the only place .gitignore lets
geojson be committed. Reads every GOGET project straight from the GEM project
database through scripts/goget_db.py (shared with build_goget_areas.py) and
writes one point per project with the handoff-schema property names the
pipeline maps already use (PipelineName, Status, Wiki, ...), so one tracker
config can drive pipelines (lines) and extraction areas (points) together.

Which projects become points, matching the data team's GOGET map export this
replaced in October 2026:

  * `goget_project.makeWIKI` is set (the export's own inclusion rule — every
    id in it carried the flag);
  * the project has coordinates;
  * it has no outline in goget_areas_latest.geojson (see outlined_project_ids),
    which is why this runs AFTER build_goget_areas.py.

Needs GEM_READONLY_DB_URL in the environment (read-only Postgres role):

    python3 scripts/build_goget_map_data.py

The open GOGET bulk-upload requests in the Asana Data team inbox are overlaid
on the database (moved locations, operators, status, production, deletions,
plus brand-new assets that have no GEM id yet) — see
scripts/goget_bulk_overlay.py; fill `_asana_cache/` with
scripts/asana_goget_bulk_uploads.py first.

Commit and push the regenerated goget_map_latest.geojson; the ggit-goget map
loads it from this repo's raw.githubusercontent.com URL.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import goget_db
from goget_bulk_overlay import BulkOverlay

OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget' / 'goget_map_latest.geojson'
AREAS_PATH = OUT_PATH.parent / 'goget_areas_latest.geojson'

# ~0.1 m at the equator; the database stores more digits than that.
COORD_PRECISION = 6


def outlined_project_ids():
    """ProjectIDs that already have a field outline on the map.

    An extraction area should be one asset, so where build_goget_areas.py
    produced an outline the centroid is dropped. Keeping both would count those
    fields twice in the legend and the 'total assets' line: the shell groups
    features by link field *plus* coordinates, and a polygon's coordinates are a
    ring array, so an outline and its own centroid never collapse into one
    asset. The outlines carry the same production, capacity and parent, so
    dropping the point loses nothing.
    """
    if not AREAS_PATH.exists():
        print(f'{AREAS_PATH.name} not found — keeping every centroid')
        return set()
    data = json.loads(AREAS_PATH.read_text())
    ids = {f['properties'].get('ProjectID') for f in data['features']}
    return ids - {'', None}


def main():
    bulk = BulkOverlay.load()
    print('\n'.join(bulk.describe()))
    outlined = outlined_project_ids()

    projects = goget_db.fetch_projects()
    production, skipped = goget_db.production_by_project()
    parents = goget_db.parents_by_project()
    print(f'fetched {len(projects)} GOGET projects')
    print('\n'.join(goget_db.describe_skipped(skipped)))

    features = []
    counts = {'not flagged for a wiki page': 0, 'no coordinates': 0, 'outlined instead': 0}
    overlaid = {'deleted': 0, 'location': 0, 'operator': 0, 'status': 0, 'production': 0}
    for project_id, row in projects.items():
        if project_id in bulk.deleted:
            overlaid['deleted'] += 1
            continue
        if not row['make_wiki']:
            counts['not flagged for a wiki page'] += 1
            continue
        if project_id in outlined:
            counts['outlined instead'] += 1
            continue
        if row['latitude'] is None or row['longitude'] is None:
            if project_id not in bulk.latlon:
                counts['no coordinates'] += 1
                continue
            geometry = {'type': 'Point', 'coordinates': []}  # filled by the bulk upload below
        else:
            geometry = {'type': 'Point', 'coordinates': [round(float(row['longitude']), COORD_PRECISION),
                                                          round(float(row['latitude']), COORD_PRECISION)]}
        props = goget_db.feature_props(row)
        props.update(goget_db.point_only_props(project_id, production, parents))
        out_feature = {'type': 'Feature', 'geometry': geometry, 'properties': props}
        overlaid['location'] += bulk.apply_latlon(out_feature, project_id)
        if not out_feature['geometry']['coordinates']:
            counts['no coordinates'] += 1
            continue
        overlaid['operator'] += bulk.apply_operator(props, project_id)
        # the bulk entries are merged into the full database timeline so the
        # status is read the same way as everywhere else
        overlaid['status'] += bulk.apply_status(props, project_id, row['timeline'])
        overlaid['production'] += bulk.apply_production(props, project_id)
        features.append(out_feature)

    template = {k: '' for k in features[0]['properties']} if features else {}
    new_features = bulk.new_asset_features(template)
    features.extend(new_features)

    out = {'type': 'FeatureCollection', 'features': features}
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f'wrote {OUT_PATH.name}: {len(features)} features, {size_mb:.1f} MB')
    print('left out: ' + ', '.join(f'{v} {k}' for k, v in counts.items()))
    if not bulk.empty:
        print('bulk uploads applied: ' + ', '.join(f'{k} {v}' for k, v in overlaid.items())
              + f', new assets added {len(new_features)}')


if __name__ == '__main__':
    main()
