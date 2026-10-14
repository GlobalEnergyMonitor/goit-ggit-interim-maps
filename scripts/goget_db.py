#!/usr/bin/env python3
"""GEM database reads shared by the two GOGET map builders.

build_goget_areas.py (field outlines) and build_goget_map_data.py (centroids)
both draw on the same project rows, production figures and parent strings, so
they live here rather than in one builder importing the other. Everything comes
from the read-only GEM connection in scripts/gem_db.py (borrowed from the
sibling gem-db-ops repo); nothing here writes.

  * projects: gem-db-ops' `export_goget_all_fields`, the port of the
    website's GOGET all-fields report (one row per non-deleted
    `plant.projectType = 9` plant), written to a temporary CSV — the same
    pattern build_gogpt_map_data.py uses. Name, wiki link, location, outline,
    operators, status and the discovery / FID / production-start years are
    therefore spelled the way the published spreadsheet spells them
    (status and years read off the timeline the website's way, so a field
    whose only operating entry is an as-of year has no production start
    year). Before 2026-10-14 this module ran its own project query instead.
  * what the export doesn't carry, or carries in a form the map can't use,
    comes from EXTRA_QUERY: the second country; the owners with their shares
    as recorded (the export truncates them to whole numbers, which turns a
    0.74% stake into "[0%]"; the map keeps the decimals); the decimal
    coordinates (a fallback for the few rows whose export coordinates are free
    text); the raw status timeline (the Asana bulk overlay merges its entries
    into it); and when the outline was last edited (the overlay's newer-source
    check).
  * parents: the owner companies' precomputed ultimate parents
    (`company.gemParentsJSON`), the owner's share times the chain share,
    summed per parent, one decimal, biggest first; an owner with no recorded
    share lists its parents without a bracket. GOGET's all-fields report has
    no parent column, so this stays here. Checked against the March 2026 CDN
    export: 5,927 of 7,673 strings identical, the rest mostly company renames
    since then.
  * production: `reserves_production` rows of kind 'production', converted
    with goget_bulk_overlay.convert_production (oil and condensate to million
    bbl/y, gas to million m³/y), latest year per fuel, summed within that year.
    The export only gives the latest year, not the quantities. Checked against
    the March 2026 CDN export: within rounding on ~3,150 of ~3,350 projects
    per fuel, the rest being figures updated since March. Fuels and units the
    conversion doesn't cover (LPG, NGL, boe, petajoules…) are skipped and
    counted, never guessed.
"""

import csv
import json
import sys
import tempfile
from collections import Counter, defaultdict
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gem_db  # read-only GEM connection, borrowed from the sibling gem-db-ops repo
from goget_bulk_overlay import NO_STATUS, convert_production, production_props

csv.field_size_limit(sys.maxsize)  # the outline column runs to ~2 MB

GOGET_PROJECT_TYPE = 9

# The properties only the point builder used to have (copied off the export);
# now both builders fill them from the database. The map needs them
# present-but-empty rather than absent: Capacity and CapacityUnits are table
# columns.
POINT_ONLY_FIELDS = (
    'Parent',
    'ProdOil', 'ProdOilYear', 'ProdGas', 'ProdGasYear',
    'Capacity', 'CapacityUnits', 'CapacityBOEd',
)

# One row per GOGET plant, keyed like the export's "Unit ID". The outline row
# is the lowest-id one, the same row the export prints.
EXTRA_QUERY = """
with owners as (
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
geo as (
    select distinct on (pg.project_id) pg.project_id, pg.modified
    from project_geospatial pg
    order by pg.project_id, pg.id
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
select 'L' || p.id          as project_id,
       c2."gemName"         as country2,
       owners.owners,
       p.latitude,
       p.longitude,
       tl.timeline,
       geo.modified         as wkt_modified
from plant p
left join country c2 on c2.id = p.country2_id
left join owners on owners.plant_id = p.id
left join tl on tl.plant_id = p.id
left join geo on geo.project_id = p.id
where p.deleted is not true
  and p."projectType" = :project_type
"""


OWNER_QUERY = """
select 'L' || p.id as project_id,
       po.share,
       c."gemParentsJSON"
from plant p
join plant_owner po on po.plant_id = p.id
join company c on c.id = po.company_id and c.deleted is not true
where p.deleted is not true
  and p."projectType" = :project_type
order by po.id
"""

PRODUCTION_QUERY = """
select 'L' || p.id as project_id,
       rp."fuelDesc",
       rp.quantity,
       rp."quantityUnit",
       rp.year
from reserves_production rp
join plant p on p.id = rp.project_id
where rp."productionReserves" = 'production'
  and p.deleted is not true
  and p."projectType" = :project_type
"""


def export_rows():
    """Every row of gem-db-ops' GOGET all-fields export, as dicts keyed by the CSV header."""
    sys.path.insert(0, str(gem_db.db_ops_repo()))
    from gem_all_fields import export_goget_all_fields

    engine = gem_db.build_readonly_engine()
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / 'goget.csv'
        export_goget_all_fields(engine, str(csv_path))
        with csv_path.open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))


def _coordinate(text, fallback):
    """The export's coordinate string as a float, else the database decimal.

    The export prints the free-text `latitudeText` / `longitudeText` for
    projects recorded in another coordinate format, which may not parse.
    """
    try:
        return float(text)
    except (TypeError, ValueError):
        return float(fallback) if fallback is not None else None


def fetch_projects():
    """Every non-deleted GOGET project as a dict, by project id ('L' + plant id)."""
    extra = {row[0]: row for row in gem_db.fetch_all(EXTRA_QUERY, {'project_type': GOGET_PROJECT_TYPE})}
    projects = {}
    for row in export_rows():
        project_id = row['Unit ID']
        _, country2, owners, lat, lon, timeline, wkt_modified = extra.get(project_id, (None,) * 7)
        projects[project_id] = {
            'project_id': project_id,
            'name': row['Unit Name'],
            'wiki': row['Wiki URL'],
            'subnational': row['Subnational unit'],
            'accuracy': row['Location accuracy'],
            'country': row['Country/Area'],
            'country2': country2,
            'fuel_type': row['Fuel type'],
            'production_type': row['Production Type'],
            'basin': row['Basin'],
            'make_wiki': row['Keep (makeWIKI)'] == 'True',
            'latitude': _coordinate(row['Latitude'], lat),
            'longitude': _coordinate(row['Longitude'], lon),
            'owners': owners,
            'operators': row['Operator'],
            'status': row['Status'],
            'start_year': row['Production start year'],
            'discovery_year': row['Discovery year'],
            'fid_year': row['FID Year'],
            'timeline': timeline or [],
            'wkt': row['Project outline (WKT)'],
            'wkt_modified': wkt_modified,
        }
    return projects


def countries(country, country2):
    """Handoff schema joins multi-country projects with a comma."""
    names = [n for n in (country, country2) if n]
    return ', '.join(dict.fromkeys(names))


def feature_props(row):
    """The handoff-schema properties shared by outlines and centroids, from a fetch_projects() row.

    Status and the three year fields are the export's. A project with a bulk
    status upload gets them re-derived from the merged timeline by
    BulkOverlay.apply_status, with the export's own rules. The
    POINT_ONLY_FIELDS are added by point_only_props().
    """
    country_label = countries(row['country'], row['country2'])
    subnational = row['subnational']
    return {
        'PipelineName': row['name'] or '',
        'SegmentName': '',  # keeps the shared hover popup from printing undefined
        'Status': row['status'] or NO_STATUS,
        'Wiki': row['wiki'] or '',
        'ProjectID': row['project_id'] or '',
        'CountriesOrAreas': country_label,
        'StartState/Province': subnational or '',
        'StartLocation': ', '.join([p for p in (subnational, country_label) if p]),
        'Owner': row['owners'] or '',
        'Operator': row['operators'] or '',
        'StartYear1': row['start_year'],
        'DiscoveryYear': row['discovery_year'],
        'FIDYear': row['fid_year'],
        'LocationAccuracy': row['accuracy'] or '',
        'FuelType': row['fuel_type'] or '',
        'ProductionType': row['production_type'] or '',
        'Basin': row['basin'] or '',
        'Tracker': 'GOGET',
    }


def production_by_project():
    """{project_id: {'oil': (million bbl/y, year), 'gas': (million m³/y, year)}}.

    Latest year per fuel, rows of that year summed (a project can report several
    streams for one fuel). Returns the figures and a Counter of the
    fuel × unit combinations that were skipped, for the builders to print.
    """
    rows = gem_db.fetch_all(PRODUCTION_QUERY, {'project_type': GOGET_PROJECT_TYPE})
    by_year = defaultdict(lambda: defaultdict(float))  # (pid, category) -> {year: total}
    skipped = Counter()
    for project_id, fuel, quantity, unit, year in rows:
        if quantity is None or year is None:
            skipped[f'{fuel} {unit} (no quantity or year)'] += 1
            continue
        converted = convert_production(fuel, float(quantity), unit)
        if converted is None:
            skipped[f'{fuel} / {unit}'] += 1
            continue
        category, value = converted
        by_year[(project_id, category)][int(year)] += value
    figures = defaultdict(dict)
    for (project_id, category), years in by_year.items():
        year = max(years)
        figures[project_id][category] = (years[year], year)
    return dict(figures), skipped


def parents_by_project(engine=None):
    """{project_id: 'Parent A [60.0%]; Parent B [40.0%]'} from the owners' precomputed parent chains."""
    sys.path.insert(0, str(gem_db.db_ops_repo()))
    from gem_all_fields import _fetch_company_parent_names

    rows = gem_db.fetch_all(OWNER_QUERY, {'project_type': GOGET_PROJECT_TYPE})
    owners = defaultdict(list)
    parent_ids = set()
    for project_id, share, parents_json in rows:
        chain = parents_json if isinstance(parents_json, list) else json.loads(parents_json or '[]')
        owners[project_id].append((share, chain))
        parent_ids.update(int(p['id']) for p in chain)
    engine = engine or gem_db.build_readonly_engine()
    names = _fetch_company_parent_names(engine, sorted(parent_ids))

    out = {}
    for project_id, lst in owners.items():
        totals = {}
        unknown = set()
        for share, chain in lst:
            for parent in chain:
                key = (str(parent['id']), names.get(int(parent['id'])) or f"E{parent['id']}")
                if share is None:
                    unknown.add(key)
                    totals.setdefault(key, Decimal(0))
                else:
                    totals[key] = totals.get(key, Decimal(0)) \
                        + Decimal(share) * Decimal(str(parent['share'])) / 100
        items = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0][1].lower()))
        pieces = []
        for key, value in items:
            if key in unknown:
                pieces.append(key[1])
            else:
                shown = value.quantize(Decimal('0.1'), rounding=ROUND_HALF_EVEN)
                pieces.append(f'{key[1]} [{shown}%]')
        out[project_id] = '; '.join(pieces)
    return out


def point_only_props(project_id, production, parents):
    """The POINT_ONLY_FIELDS for one project from production_by_project() and parents_by_project()."""
    props = {'Parent': parents.get(project_id, '')}
    props.update(production_props(production.get(project_id, {})))
    return props


def describe_skipped(skipped, top=12):
    """One line per most-common skipped fuel × unit combination, for the build logs."""
    total = sum(skipped.values())
    lines = [f'production rows skipped (fuel or unit not converted): {total} in {len(skipped)} combinations']
    for combo, count in skipped.most_common(top):
        lines.append(f'  {count:5d}  {combo}')
    return lines
