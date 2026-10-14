#!/usr/bin/env python3
"""Build trackers/ggit-goget/goget_areas_latest.geojson — GOGET field outlines.

Reads the field outlines straight from the GEM project database
(`project_geospatial.wkt`, one row per project, keyed to `plant`), NOT from the
GOGET release Google Sheet. Two reasons the DB is the only acceptable source:

  * it's fresher — the sheet is a periodic release snapshot, and the researchers
    keep tracing new outlines between releases;
  * the sheet truncates. WKT longer than 32,767 characters hits Google Sheets'
    per-cell limit and comes out with unbalanced parentheses, i.e. unparseable.
    Some large fields (Tupi, Cerro Dragon, Manantiales Behr, Xanab, Marlin, and
    most of the Dutch offshore fields) are only usable from the DB.

Property names match the data-team handoff schema used by the pipeline maps and
by goget_map_latest.geojson (PipelineName, Status, Wiki, ...), so one tracker
config drives pipelines (lines), extraction points, and these outlines together.

Needs GEM_READONLY_DB_URL in the environment (read-only Postgres role):

    python3 scripts/build_goget_areas.py

The connection itself comes from the sibling gem-db-ops repo via scripts/gem_db.py
(read-only session guard + statement timeout included) — don't add a local
psycopg2.connect back.

Commit and push the regenerated file; the ggit-goget map loads it from this
repo's raw.githubusercontent.com URL.

Production, capacity and Parent come from the database too, through
scripts/goget_db.py (shared with the point builder): `reserves_production`
converted the way the data team's export did it, and the owner companies'
precomputed ultimate parents. Fuels and units the conversion doesn't cover are
skipped and listed in the build log, never guessed.

Every traced outline is included, whether or not the project carries
`goget_project.makeWIKI` (the flag the point builder, like the export it
replaced, filters on): an outline the researchers took the trouble to trace is
worth showing, and a field with an outline but no wiki page is rare. Flip the
`MAKE_WIKI_ONLY` constant below to apply the same rule here.

Run this BEFORE build_goget_map_data.py: that script reads this file to drop the
centroids of fields that now have an outline, so each extraction area is one
asset on the map instead of two.

The open GOGET bulk-upload requests in the Asana Data team inbox are overlaid on
top of the database (newer outlines, operators, status, production, deletions —
see scripts/goget_bulk_overlay.py): run scripts/asana_goget_bulk_uploads.py
first to fill `_asana_cache/`. A field that only had a centroid but gets an
outline from a bulk upload becomes an outline here, so the point builder drops
its centroid like any other.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shapely import force_2d, make_valid, set_precision
from shapely.geometry import MultiPolygon, mapping
from shapely.wkt import loads as wkt_loads

import goget_db
from goget_bulk_overlay import NO_STATUS, BulkOverlay, current_status, first_year, merge_timeline  # noqa: F401

OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget' / 'goget_areas_latest.geojson'

# Set to True to show only projects flagged for a wiki page, as the point
# builder does (see the module docstring).
MAKE_WIKI_ONLY = False

# ~0.1 m at the equator. The DB stores up to 17 significant digits per ordinate,
# which is most of the file size and none of the accuracy.
COORD_PRECISION = 6

# NO_STATUS, current_status() and first_year() live in goget_bulk_overlay so the
# point builder derives status from a merged timeline the same way.

def polygonal(geom):
    """Reduce a geometry to its polygonal parts, or None if it has none.

    Almost everything in the table is POLYGON or MULTIPOLYGON, but a couple of
    records aren't: one field is a GEOMETRYCOLLECTION wrapping its multipolygon
    (unwrapped here), and one was saved as a LINESTRING rather than a polygon.
    A closed LINESTRING is *probably* a field outline someone drew in the wrong
    geometry type, but promoting it to a polygon here would paper over a bad
    record, so it returns None and gets reported for an upstream fix instead.
    """
    if geom.geom_type in ('Polygon', 'MultiPolygon'):
        return geom
    if geom.geom_type == 'GeometryCollection':
        parts = [g for g in geom.geoms if g.geom_type in ('Polygon', 'MultiPolygon')]
        if not parts:
            return None
        polys = []
        for part in parts:
            polys.extend(part.geoms if part.geom_type == 'MultiPolygon' else [part])
        return MultiPolygon(polys)
    return None


def repair(geom):
    """Make a polygonal geometry valid, or None if nothing polygonal survives.

    Self-intersecting rings (these outlines are traced by hand, so a few cross
    themselves) render with fill artifacts in Mapbox GL. make_valid resolves
    them, but can hand back stray lines/points, so reduce again afterwards.
    """
    if geom is None or geom.is_valid:
        return geom
    return polygonal(make_valid(geom))


def snap(geom):
    """Snap ordinates to the output grid.

    This has to happen before validity is finalized: rounding coordinates merges
    near-coincident vertices, which can reintroduce exactly the
    self-intersections make_valid just resolved. set_precision rejects invalid
    input and can also fail on pathological rings, so it's guarded.
    """
    try:
        return set_precision(geom, 10 ** -COORD_PRECISION)
    except Exception:
        return geom  # leave it on the raw grid; round_coords still trims output


def round_coords(obj):
    """Round every ordinate in a GeoJSON coordinate tree."""
    if isinstance(obj, (int, float)):
        return round(obj, COORD_PRECISION)
    return [round_coords(x) for x in obj]


def main():
    bulk = BulkOverlay.load()
    print('\n'.join(bulk.describe()))
    projects = goget_db.fetch_projects()
    rows = [p for p in projects.values()
            if (p['wkt'] or p['project_id'] in bulk.wkt)
            and (p['make_wiki'] or not MAKE_WIKI_ONLY)]
    print(f'fetched {len(projects)} GOGET projects, {len(rows)} with an outline in project_geospatial or in a bulk upload')
    production, skipped = goget_db.production_by_project()
    parents = goget_db.parents_by_project()
    print('\n'.join(goget_db.describe_skipped(skipped)))

    features = []
    skipped_empty = []
    skipped_bad = []
    skipped_nonpolygon = []
    repaired_count = []
    overlaid = {'outline': 0, 'deleted': 0, 'operator': 0, 'status': 0, 'production': 0, 'outline kept (db newer)': 0}
    for row in rows:
        project_id, name, timeline, wkt, wkt_modified = (
            row['project_id'], row['name'], row['timeline'], row['wkt'], row['wkt_modified'])
        if project_id in bulk.deleted:
            overlaid['deleted'] += 1
            continue
        db_wkt = wkt
        bulk_wkt = bulk.outline(project_id, wkt_modified)
        if bulk_wkt is not None:
            wkt = bulk_wkt
            overlaid['outline'] += 1
        elif project_id in bulk.wkt:
            overlaid['outline kept (db newer)'] += 1
        if not wkt:
            continue
        try:
            geom = wkt_loads(wkt)
        except Exception as exc:  # unparseable WKT should be loud, not silent
            if bulk_wkt is not None and db_wkt:
                # a broken bulk outline shouldn't cost the field its database one
                skipped_bad.append((project_id, name, f'bulk upload WKT unparseable, kept the database outline — {exc}'[:120]))
                overlaid['outline'] -= 1
                geom = wkt_loads(db_wkt)
            else:
                skipped_bad.append((project_id, name, str(exc)[:80]))
                continue
        if geom.is_empty:
            skipped_empty.append((project_id, name))
            continue
        geom = polygonal(geom)
        if geom is None:
            skipped_nonpolygon.append((project_id, name, wkt_loads(wkt).geom_type))
            continue

        # repair -> snap to the output grid -> repair again, because snapping
        # merges near-coincident vertices and can re-break a just-fixed ring.
        was_invalid = not force_2d(geom).is_valid
        geom = repair(snap(repair(force_2d(geom))))
        if geom is None:
            skipped_bad.append((project_id, name, 'invalid geometry, unrepairable'))
            continue
        if geom.is_empty:  # snapping can collapse a sliver to nothing
            skipped_empty.append((project_id, name))
            continue
        if was_invalid:
            repaired_count.append(project_id)

        geojson_geom = mapping(geom)
        geojson_geom['coordinates'] = round_coords(geojson_geom['coordinates'])

        props = goget_db.feature_props(row)
        props.update(goget_db.point_only_props(project_id, production, parents))
        overlaid['operator'] += bulk.apply_operator(props, project_id)
        overlaid['status'] += bulk.apply_status(props, project_id, timeline)
        overlaid['production'] += bulk.apply_production(props, project_id)
        features.append({'type': 'Feature', 'geometry': geojson_geom, 'properties': props})

    out = {'type': 'FeatureCollection', 'features': features}
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))

    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f'wrote {OUT_PATH.name}: {len(features)} features, {size_mb:.1f} MB')
    print(f'{sum(bool(f["properties"]["Capacity"]) for f in features)} of them carry production/capacity, '
          f'{sum(bool(f["properties"]["Parent"]) for f in features)} a parent')
    if not bulk.empty:
        print('bulk uploads applied: ' + ', '.join(f'{k} {v}' for k, v in overlaid.items()))
    print('now rerun scripts/build_goget_map_data.py to drop the duplicated centroids')
    if repaired_count:
        print(f'repaired {len(repaired_count)} self-intersecting geometries via make_valid')
    for project_id, name in skipped_empty:
        print(f'skipped empty geometry: {project_id} {name}')
    for project_id, name, kind in skipped_nonpolygon:
        print(f'SKIPPED non-polygonal WKT ({kind}) — needs fixing in the DB: {project_id} {name}')
    for project_id, name, exc in skipped_bad:
        print(f'SKIPPED unparseable WKT: {project_id} {name} — {exc}')


if __name__ == '__main__':
    main()
