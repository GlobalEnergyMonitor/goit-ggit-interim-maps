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

Production/capacity and Parent are NOT derived from the database here; they're
copied off the data team's GOGET export instead (same SOURCE_URL that
build_goget_map_data.py uses), matched on ProjectID. Production lives in
`reserves_production` in ~110 different fuel-description × unit combinations,
including mass and energy units that need density/heat-content assumptions to
reach the map's million bbl/y and million m³/y; that normalization belongs to the
data team's export, and guessing at it would put wrong numbers on a public map.
Parent needs a real ownership-tree traversal (owner companies here have up to 528
`company_owner` edges and the `ultimateParent` flag isn't set on them), which is
the ownership repos' job. Fields the export doesn't cover simply go without.

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
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gem_db  # read-only GEM connection, borrowed from the sibling gem-db-ops repo
from shapely import force_2d, make_valid, set_precision
from shapely.geometry import MultiPolygon, mapping
from shapely.wkt import loads as wkt_loads

from build_goget_map_data import SOURCE_URL, transform
from goget_bulk_overlay import NO_STATUS, BulkOverlay, current_status, first_year, merge_timeline  # noqa: F401

OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget' / 'goget_areas_latest.geojson'

# Properties the database side can't produce (see the module docstring), taken
# from the data team's export. The map needs them present-but-empty rather than
# absent: Capacity and CapacityUnits are table columns.
POINT_ONLY_FIELDS = (
    'Parent',
    'ProdOil', 'ProdOilYear', 'ProdGas', 'ProdGasYear',
    'Capacity', 'CapacityUnits', 'CapacityBOEd',
)

# ~0.1 m at the equator. The DB stores up to 17 significant digits per ordinate,
# which is most of the file size and none of the accuracy.
COORD_PRECISION = 6

# NO_STATUS, current_status() and first_year() live in goget_bulk_overlay so the
# point builder derives status from a merged timeline the same way.

QUERY = """
with geo as (
    select pg.project_id, pg.wkt, pg.modified
    from project_geospatial pg
    where pg.wkt is not null and btrim(pg.wkt) <> ''
),
owners as (
    select po.plant_id,
           string_agg(
               btrim(c.name || ' ' || coalesce(l.type, '')) ||
               case when po.share is not null
                    -- FM trims the padding but leaves a trailing '.' on whole
                    -- numbers, so 65.00 has to come out as '65', not '65.'
                    then ' [' || rtrim(to_char(po.share, 'FM999990.99'), '.') || '%]'
                    else '' end,
               '; ' order by po.share desc nulls last, c.name
           ) as owners
    from plant_owner po
    join company c on c.id = po.company_id and c.deleted is not true
    left join legal_entity_type l on l.id = c."legalEntityType_id"
    group by po.plant_id
),
ops as (
    select o.plant_id, string_agg(distinct btrim(c.name), '; ') as operators
    from operator o
    join company c on c.id = o.company_id and c.deleted is not true
    group by o.plant_id
),
tl as (
    select u.plant_id,
           json_agg(json_build_object(
               'status', st.status, 'substatus', st.substatus,
               'ord', st."order", 'year', st.year
           ) order by st."order") as timeline
    from powerplant_unit u
    join status_timeline st on st.unit_id = u.id
    group by u.plant_id
)
select 'L' || p."unitIDSearch"[1]  as project_id,
       p."unitIDSearch"[1]          as unit_number,
       p.name,
       p."wikiUrl",
       p.subnational,
       p."locationAccuracy",
       c1."gemName"                as country,
       c2."gemName"                as country2,
       gp."fuelType",
       gp."productionType",
       gp.basin,
       owners.owners,
       ops.operators,
       tl.timeline,
       geo.wkt,
       geo.modified               as wkt_modified
from plant p
left join geo on geo.project_id = p.id
left join goget_project gp on gp.project_id = p.id
left join country c1 on c1.id = p.country_id
left join country c2 on c2.id = p.country2_id
left join owners on owners.plant_id = p.id
left join ops on ops.plant_id = p.id
left join tl on tl.plant_id = p.id
where p.deleted is not true
  and gp.project_id is not null
  and (geo.wkt is not null or p."unitIDSearch"[1] = any(:bulk_outline_ids))
order by project_id
"""


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


def countries(country, country2):
    """Handoff schema joins multi-country projects with a comma."""
    names = [n for n in (country, country2) if n]
    return ', '.join(dict.fromkeys(names))


def point_only_attributes():
    """POINT_ONLY_FIELDS from the data team's GOGET export, keyed on ProjectID.

    Read from the published export rather than the local
    goget_map_latest.geojson, because that file has had the outlined fields'
    centroids removed — the very rows this needs.
    """
    print(f'downloading {SOURCE_URL}')
    with urllib.request.urlopen(SOURCE_URL) as response:
        data = json.load(response)
    by_id = {}
    for feature in data['features']:
        props = transform(feature['properties'])
        if props['ProjectID']:
            by_id[props['ProjectID']] = {k: props[k] for k in POINT_ONLY_FIELDS}
    return by_id


def main():
    bulk = BulkOverlay.load()
    print('\n'.join(bulk.describe()))
    bulk_outline_ids = [int(u[1:]) for u in bulk.wkt if u[:1] == 'L' and u[1:].isdigit()]
    rows = gem_db.fetch_all(QUERY, {'bulk_outline_ids': bulk_outline_ids})
    print(f'fetched {len(rows)} fields with an outline in project_geospatial or in a bulk upload')

    point_attrs = point_only_attributes()
    blank_attrs = {k: '' for k in POINT_ONLY_FIELDS}
    matched = 0

    features = []
    skipped_empty = []
    skipped_bad = []
    skipped_nonpolygon = []
    repaired_count = []
    overlaid = {'outline': 0, 'deleted': 0, 'operator': 0, 'status': 0, 'production': 0, 'outline kept (db newer)': 0}
    for (project_id, unit_number, name, wiki, subnational, accuracy, country, country2,
         fuel_type, production_type, basin, owners, operators, timeline, wkt, wkt_modified) in rows:
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

        status = current_status(timeline)
        country_label = countries(country, country2)
        extras = point_attrs.get(project_id)
        matched += extras is not None

        props = {
            'PipelineName': name or '',
            'SegmentName': '',  # keeps the shared hover popup from printing undefined
            'Status': status,
            'Wiki': wiki or '',
            'ProjectID': project_id or '',
            'CountriesOrAreas': country_label,
            'StartState/Province': subnational or '',
            'StartLocation': ', '.join([p for p in (subnational, country_label) if p]),
            'Owner': owners or '',
            'Operator': operators or '',
            'StartYear1': first_year(timeline, status='operating'),
            'DiscoveryYear': first_year(timeline, status='discovered'),
            'FIDYear': first_year(timeline, substatus='actual FID'),
            'LocationAccuracy': accuracy or '',
            'FuelType': fuel_type or '',
            'ProductionType': production_type or '',
            'Basin': basin or '',
            'Tracker': 'GOGET',
            **(extras or blank_attrs),
        }
        overlaid['operator'] += bulk.apply_operator(props, project_id)
        overlaid['status'] += bulk.apply_status(props, project_id, timeline)
        overlaid['production'] += bulk.apply_production(props, project_id)
        features.append({'type': 'Feature', 'geometry': geojson_geom, 'properties': props})

    out = {'type': 'FeatureCollection', 'features': features}
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))

    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f'wrote {OUT_PATH.name}: {len(features)} features, {size_mb:.1f} MB')
    print(f'{matched} of them picked up production/capacity/parent from the export')
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
