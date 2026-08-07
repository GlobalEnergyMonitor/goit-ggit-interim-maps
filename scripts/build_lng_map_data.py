#!/usr/bin/env python3
"""Build trackers/ggit-goget-gogpt/lng_map_latest.geojson — GGIT LNG terminals.

Read straight from the GEM project database, like build_goget_areas.py: there is
no published LNG map export on the CDN to rename, and the DB is the live source
the researchers work in. (gem-db-ops/lng/pull.py exports the same tracker as the
website's 115-column all-fields CSV; this script pulls only the dozen or so
columns the map draws, so the two don't have to stay in step.)

Needs GEM_READONLY_DB_URL in the environment (read-only Postgres role):

    python3 scripts/build_lng_map_data.py

Commit and push the regenerated file; the ggit-goget-gogpt map loads it from
this repo's raw.githubusercontent.com URL.

Features are UNIT-level, one per terminal unit, but every unit carries its
terminal's coordinates (the DB holds location on the project, not the unit), so
the shell's linkField + coordinates grouping collapses a terminal into a single
map marker and the detail card lists its units. Terminals with no coordinates
are skipped and reported.

This tracker is deliberately NOT added to the ggit map, which is gas pipelines
only — terminals appear on the combined ggit-goget-gogpt map.
"""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import psycopg2

OUT_PATH = Path(__file__).resolve().parent.parent / 'trackers' / 'ggit-goget-gogpt' / 'lng_map_latest.geojson'

# plant."projectType" for the LNG tracker (see PROJECT_TYPES in gem-db-ops/gem_query.py)
LNG_PROJECT_TYPE = 8

# Capacity arrives in whatever unit the researcher recorded, so the map's shared
# circle-scaling field needs one common number. CapacityMapScale is in boe/d,
# the same display-only field the pipelines and extraction areas use.
#
# 1 Mtpa LNG = 1e6 t/y x 52 GJ/t / 6.1178 GJ per boe / 365 d = ~23,300 boe/d.
# Oil throughput in bbl/d is boe/d by definition. Everything else (TJ/d, MWh/d,
# tpa of hydrogen/ammonia, and the rows whose unit was left blank) is left
# unscaled rather than guessed at — those terminals draw at the minimum radius.
# The recorded figures always stay in Capacity/CapacityUnits, which is what the
# detail card, the table and the downloads report.
MTPA_TO_BOED = Decimal('23300')
MTPA_PER_BCM = Decimal('0.735')  # the LNG tracker's own bcm/y <-> mtpa factor

CAPACITY_UNIT_TO_MTPA = {
    'mtpa': Decimal('1'),
    'bcm/y': MTPA_PER_BCM,
    'bcm': MTPA_PER_BCM,
    'bcma': MTPA_PER_BCM,
    'bcf/d': Decimal('7.67'),
    'mmcf/d': Decimal('0.00767'),
}

# Units that are already an oil-equivalent rate, converted straight to boe/d.
CAPACITY_UNIT_TO_BOED = {
    'bpd': Decimal('1'),
    'gal/day': Decimal('1') / Decimal('42'),
}

QUERY = f"""
with owners as (
    select po.plant_id,
           string_agg(
               btrim(c.name || ' ' || coalesce(l.type, '')) ||
               case when po.share is not null
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
    select st.unit_id,
           json_agg(json_build_object(
               'status', st.status, 'substatus', st.substatus,
               'ord', st."order", 'year', st.year
           ) order by st."order") as timeline
    from status_timeline st
    group by st.unit_id
)
select 'T' || p.id            as terminal_id,
       'G' || pu.id           as unit_id,
       p.name                 as terminal_name,
       pu.name                as unit_name,
       p."wikiUrl"            as wiki,
       p.latitude             as latitude,
       p.longitude            as longitude,
       p.subnational          as subnational,
       p."locationAccuracy"   as accuracy,
       c."gemName"            as country,
       lu."facilityType"      as facility_type,
       lu.fuel                as fuel,
       lu.capacity            as capacity,
       lu."capacityUnit"      as capacity_unit,
       owners.owners          as owners,
       ops.operators          as operators,
       tl.timeline            as timeline
from plant p
join powerplant_unit pu on pu.plant_id = p.id and pu.deleted is not true
left join lng_unit lu on lu.unit_id = pu.id
left join country c on c.id = p.country_id
left join owners on owners.plant_id = p.id
left join ops on ops.plant_id = p.id
left join tl on tl.unit_id = pu.id
where p."projectType" = {LNG_PROJECT_TYPE} and p.deleted is not true
order by p.name, pu.id
"""

# What the map's shared status vocabulary uses for a unit with no timeline. An
# empty string would fall through color_association to black and match no legend
# checkbox.
NO_STATUS = 'not found'


def current_status(timeline):
    """Current lifecycle status from the timeline.

    Same rule the website's export uses: the highest-`order` entry, skipping
    planned future events (a scheduled start-up) and FID, which is a milestone
    rather than a status.
    """
    if not timeline:
        return NO_STATUS
    def is_current(entry):
        return ((entry.get('substatus') or '').lower() != 'planned'
                and (entry.get('status') or '').lower() != 'fid')
    ordered = sorted(timeline, key=lambda t: (t.get('ord') is None, t.get('ord')))
    candidates = [t for t in ordered if is_current(t)]
    if not candidates:
        candidates = [t for t in ordered if (t.get('status') or '').lower() != 'fid'] or ordered
    return (candidates[-1].get('status') or '').strip() or NO_STATUS


def first_year(timeline, status):
    """Year of the earliest actual (not planned) entry with this status."""
    matches = [
        t for t in timeline or []
        if (t.get('status') or '').strip() == status
        and (t.get('substatus') or '').lower() != 'planned'
        and t.get('year')
    ]
    if not matches:
        return ''
    matches.sort(key=lambda t: (t.get('ord') is None, t.get('ord')))
    return str(matches[0]['year'])


def map_scale(capacity, unit):
    """Capacity as boe/d for circle scaling, or '' if the unit isn't convertible."""
    if capacity is None:
        return ''
    key = (unit or '').strip().lower()
    if key in CAPACITY_UNIT_TO_MTPA:
        return float(round(Decimal(capacity) * CAPACITY_UNIT_TO_MTPA[key] * MTPA_TO_BOED, 1))
    if key in CAPACITY_UNIT_TO_BOED:
        return float(round(Decimal(capacity) * CAPACITY_UNIT_TO_BOED[key], 1))
    return ''


def trim(value):
    """Decimals come back as '9.50'; the map shows them verbatim."""
    if value is None:
        return ''
    text = str(value)
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def main():
    db_url = os.environ.get('GEM_READONLY_DB_URL')
    if not db_url:
        sys.exit('GEM_READONLY_DB_URL is not set (read-only GEM project DB URL)')

    with psycopg2.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(QUERY)
        rows = cur.fetchall()
    print(f'fetched {len(rows)} LNG terminal units')

    features = []
    no_coords = []
    unscaled = 0
    for (terminal_id, unit_id, terminal_name, unit_name, wiki, latitude, longitude,
         subnational, accuracy, country, facility_type, fuel, capacity,
         capacity_unit, owners, operators, timeline) in rows:
        if latitude is None or longitude is None:
            no_coords.append((terminal_id, terminal_name))
            continue

        status = current_status(timeline)
        scale = map_scale(capacity, capacity_unit)
        unscaled += scale == ''
        # '--' is the tracker's placeholder for a terminal with a single unnamed unit
        unit_label = (unit_name or '').strip()
        if unit_label in ('', '--'):
            unit_label = ''

        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [float(longitude), float(latitude)]},
            'properties': {
                'PipelineName': terminal_name or '',
                'SegmentName': f'Unit {unit_label}' if unit_label else '',
                'Status': status,
                'Wiki': wiki or '',
                'ProjectID': terminal_id or '',
                'UnitID': unit_id or '',
                'CountriesOrAreas': country or '',
                'StartState/Province': subnational or '',
                'StartLocation': ', '.join([p for p in (subnational, country) if p]),
                'Owner': owners or '',
                'Operator': operators or '',
                'StartYear1': first_year(timeline, 'operating'),
                'FuelType': fuel or '',
                'FacilityType': facility_type or '',
                'LocationAccuracy': accuracy or '',
                'Capacity': trim(capacity),
                'CapacityUnits': capacity_unit or '',
                'CapacityMapScale': scale,
                'Tracker': 'GGIT-LNG',
            },
        })

    out = {'type': 'FeatureCollection', 'features': features}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, separators=(',', ':'), ensure_ascii=False))

    size_mb = OUT_PATH.stat().st_size / 1e6
    terminals = len({f['properties']['ProjectID'] for f in features})
    print(f'wrote {OUT_PATH.name}: {len(features)} units at {terminals} terminals, {size_mb:.1f} MB')
    print(f'{unscaled} units have a capacity unit that does not convert to boe/d '
          f'(they draw at the minimum radius)')
    for terminal_id, name in no_coords:
        print(f'skipped (no coordinates in the DB): {terminal_id} {name}')


if __name__ == '__main__':
    main()
