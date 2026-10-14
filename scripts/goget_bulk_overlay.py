#!/usr/bin/env python3
"""Overlay the GOGET bulk uploads waiting in Asana onto the map's GOGET data.

Researchers hand GOGET updates to the data team as CSV bulk-upload requests in
the Asana "Data team inbox" (one task per region, files on subtasks). Until the
data team processes a request its contents aren't in the GEM database, yet they
are the freshest GOGET data there is: outlines, locations, production, operators,
status, deletions. scripts/asana_goget_bulk_uploads.py downloads the files of
every *open* request into a cache directory; this module reads that cache and
lets the two GOGET builders apply the files on top of what the database and the
data team's export say.

The requests belong to the data team and are never modified (let alone
completed) by anything here — this is read-only, and the Asana script only
ever issues GET requests.

What is applied, keyed on the GEM unit id (L1000…):

  * field outlines (WKT) — replace the database outline, or give an outline to
    a field that only had a centroid, unless the database row was modified
    after the file was uploaded (then the database is the newer source);
  * point locations (lat/lon + accuracy + subnational) — move centroids;
  * operators (GEM entity ids, resolved to names through the `company` table);
  * status timeline entries — merged into the database timeline, then the
    status and years are re-derived by the export's rules (timeline_props);
  * production — the same conversion the database builders use for
    `reserves_production` (convert_production below): oil and condensate in
    bbl, m³ or tonnes, gas in m³ or cubic feet (standard/normal variants,
    thousand/million/billion prefixes, bcm, per year or per day), normalized
    to million bbl/y and million m³/y and summed into the million boe/y
    capacity. Reserves, cumulative production, LPG, NGL and energy units are
    reported and skipped;
  * deletions — the feature is dropped;
  * brand-new assets without a GEM id yet (name + coordinates) — added as
    centroids with an empty wiki link.

Other IDs, "record of full updates" and the Make_wiki/Keep flags don't show on
the map and are ignored. When the same unit appears in several files the newest
file (by attachment date) wins.

Cache location: `_asana_cache/` beside `trackers/` (gitignored), or
$GOGET_BULK_CACHE. No cache means no overlay — the builders then behave as
before and say so.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = REPO_ROOT / '_asana_cache'
CACHE_ENV_VAR = 'GOGET_BULK_CACHE'
MANIFEST_NAME = 'manifest.json'
# Bulk files Asana links as Google Sheets rather than attaching as CSVs: CI has no
# Google login, so these are exported by hand into the repo (same manifest format)
STATIC_DIR = REPO_ROOT / 'data' / 'goget_bulk_static'

csv.field_size_limit(sys.maxsize)  # WKT cells run to hundreds of KB

# What the data team's own GOGET export uses for a field with no recorded
# status. An empty string would fall through the map's color_association to
# black and match no legend checkbox, so it has to be a value the shared status
# vocabulary already knows.
NO_STATUS = 'not found'

# Columns that carry the GEM unit id, in the order they're tried.
ID_COLUMNS = ('Unit ID', 'Project ID', 'Database ID', 'GEM Project ID')

# The data team's export used these factors (checked against its March 2026
# GOGET map export, which the database builders replaced in October 2026):
# gas / (capacity - oil) is 169.9813 m³ per boe (6,000 cf/boe) on every row
# that reports both fuels, and oil or condensate recorded by mass comes out at
# 7.33 bbl per tonne.
M3_PER_BOE = 169.9813
BBL_PER_M3 = 6.28981
BBL_PER_TONNE = 7.33
M3_PER_CUBIC_FOOT = 0.0283168
MILLION_BOE_Y_TO_BOE_D = 1e6 / 365.0

# Fuel descriptions folded into the map's two production figures. Condensate
# counts as oil, as it did in the data team's export. Anything else (LPG, NGL,
# bitumen, coal seam gas, hydrocarbons in boe…) is reported as skipped rather
# than guessed.
OIL_FUELS = {'oil', 'crude oil', 'crude', 'oil and condensate', 'crude oil and condensate',
             'condensate', 'gas condensate', 'oil and gas condensate', 'oil (incl. condensate)'}
GAS_FUELS = {'gas', 'natural gas', 'dry gas', 'associated gas', 'non-associated gas',
             'nonassociated gas', 'non associated gas', 'sales gas', 'raw gas',
             'marketable gas', 'wet gas', 'gas (incl. associated gas)',
             'coal seam gas', 'coal bed methane'}

# Volume units, plus mass units for oil. Standard/normal cubic meters (Sm³,
# Nm³, m³(Vn), "metric standard m³") are the map's m³; scf is cf; bcm is a
# billion m³; a megalitre is 1,000 m³. Energy units (petajoules, boe) and
# anything unrecognized are skipped.
UNIT_RE = re.compile(
    r'^(?:(?P<prefix>thousand|kilo|million|billion)\s*)?'
    r'(?:metric\s*standard\s*)?'
    r'(?P<unit>[sn]?m³|[sn]?m3|m³\(vn\)|m3\(vn\)|cubic\s*met(?:re|er)s?|stb|bbls?|barrels?'
    r'|cubic\s*feet|cubic\s*foot|s?cf|mcf|mmcf|bcf|bcm'
    r'|megalit(?:re|er)s?|kilolit(?:re|er)s?|lit(?:re|er)s?'
    r'|(?:metric\s*)?tonnes?|(?:metric\s*)?tons?|t|kilotonnes?|kt)'
    r'\s*(?:/\s*(?P<period>y|yr|year|a|d|day))?$',
    re.IGNORECASE,
)
PREFIX_SCALE = {None: 1.0, 'thousand': 1e3, 'kilo': 1e3, 'million': 1e6, 'billion': 1e9}

# Bulk files spell a few statuses differently from the database.
STATUS_ALIASES = {'in development': 'in-development'}


def _norm(text):
    return (text or '').strip()


def _lower(text):
    return _norm(text).lower()


# ---------------------------------------------------------------------------
# Timeline helpers (shared with the database builders)
# ---------------------------------------------------------------------------

def timeline_props(timeline):
    """Status and the three year properties from a timeline, the export's way.

    Runs gem-db-ops' _derive_goget_status, the port of the website's GOGET
    status logic that also fills the all-fields export the builders read, so a
    project whose timeline gained bulk-upload entries is read by the same rules
    as every other project: the latest non-planned entry is the status;
    discovery, FID and production start are the first dated entries of the
    first discovered, non-planned in-development and operating + ramp up
    groups. A timeline with only planned entries has no status.
    """
    import gem_db
    sys.path.insert(0, str(gem_db.db_ops_repo()))
    from gem_all_fields import _derive_goget_status, _fmt_year

    derived = _derive_goget_status([
        {'order': t.get('ord') or 0, 'status': (t.get('status') or '').strip(),
         'substatus': (t.get('substatus') or '').strip(), 'year': t.get('year')}
        for t in timeline or []
    ])
    return {
        'Status': derived['status'] or NO_STATUS,
        'StartYear1': _fmt_year(derived['start_year']),
        'DiscoveryYear': _fmt_year(derived['discovery_year']),
        'FIDYear': _fmt_year(derived['fid_year']),
    }


def merge_timeline(db_timeline, bulk_entries):
    """Database timeline plus the bulk-upload entries, in researcher order.

    Bulk entries are appended after the database ones (they're the newer
    research), skipping any that duplicate an existing status/substatus/year.
    """
    merged = list(db_timeline or [])
    seen = {((t.get('status') or '').strip(), (t.get('substatus') or '').strip(), t.get('year'))
            for t in merged}
    next_ord = max((t.get('ord') or 0 for t in merged), default=0) + 1
    for entry in bulk_entries:
        key = (entry['status'], entry['substatus'], entry['year'])
        if key in seen:
            continue
        seen.add(key)
        merged.append({'status': entry['status'], 'substatus': entry['substatus'],
                       'ord': next_ord, 'year': entry['year']})
        next_ord += 1
    return merged


# ---------------------------------------------------------------------------
# Parsing the cache
# ---------------------------------------------------------------------------

def parse_timestamp(value):
    """Asana's ISO timestamps -> aware datetime (naive input is taken as UTC)."""
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def classify(header):
    """File type from the CSV header; None for files the map can't use."""
    cols = {_norm(c) for c in header}
    has_id = any(c in cols for c in ID_COLUMNS)
    if 'Project outline (WKT)' in cols or 'WKT' in cols:
        return 'wkt'
    if 'Latitude' in cols and 'Longitude' in cols:
        return 'latlon' if has_id else 'new_asset'
    if 'Quantity Unit' in cols:
        return 'production'
    if has_id and ('Operator' in cols or 'Operator GEM Entity ID' in cols):
        return 'operator'
    if has_id and 'Status' in cols:
        return 'status'
    if has_id and len(cols) == 1:
        return 'deletion'
    return None


def read_table(path, max_preamble=10):
    """(header, rows) from a bulk CSV.

    Some files still carry the upload template's title and instruction lines
    above the real header, so take the first of the top few lines that
    classify() recognizes, falling back to the first line.
    """
    with open(path, newline='', encoding='utf-8-sig') as handle:
        lines = list(csv.reader(handle))
    start = next((i for i, line in enumerate(lines[:max_preamble]) if classify(line)), 0)
    header = [_norm(c) for c in lines[start]] if lines else []
    rows = []
    for line in lines[start + 1:]:
        if any(cell.strip() for cell in line):
            rows.append({k: v for k, v in zip(header, line) if k})
    return header, rows


def unit_id(row):
    for col in ID_COLUMNS:
        value = _norm(row.get(col))
        if value:
            return value
    return ''


def government_id_key(row):
    """Production key for a new asset that has no GEM id yet: its temporary
    government unit id, a column whose header starts 'Government unit ID'."""
    for col, value in row.items():
        if col.startswith('Government unit ID') and _norm(value):
            return 'gov:' + _norm(value)
    return ''


def parse_quantity(text):
    try:
        return float(_norm(text).replace(',', ''))
    except ValueError:
        return None


def convert_production(fuel, quantity, unit):
    """Bulk row -> ('oil', million bbl/y) or ('gas', million m³/y), or None."""
    fuel_key = _lower(fuel)
    if fuel_key in OIL_FUELS:
        category = 'oil'
    elif fuel_key in GAS_FUELS:
        category = 'gas'
    else:
        return None
    match = UNIT_RE.match(_lower(unit))
    if not match or not match.group('period'):
        return None  # reserves / cumulative figures have no period
    base = match.group('unit').replace(' ', '')
    scale = PREFIX_SCALE[(match.group('prefix') or '').lower() or None]
    if base == 'mcf':
        base, scale = 'cubicfeet', scale * 1e3
    elif base == 'mmcf':
        base, scale = 'cubicfeet', scale * 1e6
    elif base == 'bcf':
        base, scale = 'cubicfeet', scale * 1e9
    elif base == 'bcm':
        base, scale = 'm3', scale * 1e9
    elif base.startswith('megalit'):
        base, scale = 'm3', scale * 1e3
    elif base.startswith('kilolit'):
        base = 'm3'
    elif base.startswith('lit'):
        base, scale = 'm3', scale * 1e-3
    elif base in ('kilotonne', 'kilotonnes', 'kt'):
        base, scale = 'tonne', scale * 1e3
    elif base.startswith('bbl') or base.startswith('barrel') or base == 'stb':
        base = 'bbl'
    elif base.startswith('cubicmet') or base.rstrip('(vn)') in ('m3', 'm³', 'sm3', 'sm³', 'nm3', 'nm³'):
        base = 'm3'
    elif base in ('cf', 'scf', 'cubicfeet', 'cubicfoot'):
        base = 'cubicfeet'
    elif base in ('tonne', 'tonnes', 'ton', 'tons', 'metrictonne', 'metrictonnes',
                  'metricton', 'metrictons', 't'):
        base = 'tonne'
    per_year = quantity * scale
    if match.group('period').lower().startswith('d'):
        per_year *= 365.0
    if category == 'oil':
        if base == 'bbl':
            value = per_year
        elif base == 'm3':
            value = per_year * BBL_PER_M3
        elif base == 'tonne':
            value = per_year * BBL_PER_TONNE
        else:
            return None
    else:
        if base == 'm3':
            value = per_year
        elif base == 'cubicfeet':
            value = per_year * M3_PER_CUBIC_FOOT
        else:
            return None
    return category, value / 1e6


def capacity_from_production(oil, gas):
    """Capacity / CapacityUnits / CapacityBOEd from the two production figures.

    Oil in million bbl/y plus gas in million m³/y over the export's m³-per-boe
    factor, in million boe/y; CapacityBOEd is the same figure as boe/d, which
    is what the pipeline features carry, so the circle scaling stays
    comparable. Empty when neither fuel has a figure.
    """
    if oil in ('', None) and gas in ('', None):
        return {'Capacity': '', 'CapacityUnits': '', 'CapacityBOEd': ''}
    capacity = (float(oil) if oil not in ('', None) else 0.0) \
        + (float(gas) if gas not in ('', None) else 0.0) / M3_PER_BOE
    return {
        'Capacity': f'{capacity:.4f}'.rstrip('0').rstrip('.'),
        'CapacityUnits': 'million boe/y',
        'CapacityBOEd': round(capacity * MILLION_BOE_Y_TO_BOE_D, 1),
    }


def production_props(figures):
    """The seven production properties from {'oil': (value, year), 'gas': (value, year)}."""
    props = {'ProdOil': '', 'ProdOilYear': '', 'ProdGas': '', 'ProdGasYear': ''}
    if 'oil' in figures:
        props['ProdOil'] = round(figures['oil'][0], 3)
        props['ProdOilYear'] = str(figures['oil'][1])
    if 'gas' in figures:
        props['ProdGas'] = round(figures['gas'][0], 3)
        props['ProdGasYear'] = str(figures['gas'][1])
    props.update(capacity_from_production(props['ProdOil'], props['ProdGas']))
    return props


class BulkOverlay:
    """Everything the open bulk-upload requests say, newest file per unit."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.files = []            # manifest entries that were parsed, with 'kind'
        self.ignored = []          # manifest entries with no map-relevant content
        self.wkt = {}              # id -> (stamp, wkt, datasource)
        self.latlon = {}           # id -> (stamp, lat, lon, accuracy, subnational)
        self.operator = {}         # id -> (stamp, [entity ids])
        self.status = {}           # id -> (stamp, [entries])
        self.production = {}       # id -> (stamp, {'oil': (value, year), 'gas': (value, year)})
        self.deleted = {}          # id -> stamp
        self.new_assets = []       # (stamp, row dict)
        self.skipped_production = Counter()   # (fuel, unit, kind) -> rows
        self._company_names = None

    # -- loading ------------------------------------------------------------

    @classmethod
    def load(cls, cache_dir=None):
        cache_dir = Path(cache_dir or os.environ.get(CACHE_ENV_VAR) or DEFAULT_CACHE_DIR)
        overlay = cls(cache_dir)
        entries = []
        for base in (cache_dir, STATIC_DIR):
            manifest = base / MANIFEST_NAME
            if manifest.is_file():
                entries += [(base, e) for e in json.loads(manifest.read_text())]
        entries.sort(key=lambda be: be[1]['created_at'])  # oldest first: later files override
        for base, entry in entries:
            path = base / entry['path']
            if not path.is_file():
                print(f'bulk upload: missing cached file {path.name} ({entry["name"]}) — skipped')
                continue
            header, rows = read_table(path)
            kind = classify(header)
            record = {**entry, 'kind': kind, 'rows': len(rows)}
            if kind is None:
                self_ignored = overlay.ignored
                self_ignored.append(record)
                continue
            overlay.files.append(record)
            getattr(overlay, f'_take_{kind}')(parse_timestamp(entry['created_at']), rows, entry)
        return overlay

    @property
    def empty(self):
        return not self.files

    @staticmethod
    def _put(store, key, stamp, value):
        current = store.get(key)
        if current is None or stamp >= current[0]:
            store[key] = (stamp, *value) if isinstance(value, tuple) else (stamp, value)

    def _take_wkt(self, stamp, rows, entry):
        for row in rows:
            uid = unit_id(row)
            wkt = _norm(row.get('Project outline (WKT)') or row.get('WKT'))
            if uid and wkt:
                self._put(self.wkt, uid, stamp, (wkt, _norm(row.get('WKT datasource'))))

    def _take_latlon(self, stamp, rows, entry):
        for row in rows:
            uid = unit_id(row)
            lat, lon = parse_quantity(row.get('Latitude')), parse_quantity(row.get('Longitude'))
            if uid and lat is not None and lon is not None:
                self._put(self.latlon, uid, stamp,
                          (lat, lon, _lower(row.get('Location accuracy')), _norm(row.get('Subnational'))))

    def _take_operator(self, stamp, rows, entry):
        per_unit = defaultdict(list)
        for row in rows:
            uid = unit_id(row)
            entity = _norm(row.get('Operator GEM Entity ID') or row.get('Operator'))
            if uid and entity and entity not in per_unit[uid]:
                per_unit[uid].append(entity)
        for uid, entities in per_unit.items():
            self._put(self.operator, uid, stamp, entities)

    def _take_status(self, stamp, rows, entry):
        per_unit = defaultdict(list)
        for row in rows:
            uid = unit_id(row)
            status = _lower(row.get('Status'))
            status = STATUS_ALIASES.get(status, status)
            if not uid or not status:
                continue
            substatus = _lower(row.get('Sub Status') or row.get('Sub status') or row.get('Status detail'))
            year = parse_quantity(row.get('Year') or row.get('Status year'))
            per_unit[uid].append({'status': status, 'substatus': substatus,
                                  'year': int(year) if year else None})
        for uid, entries in per_unit.items():
            self._put(self.status, uid, stamp, entries)

    def _take_production(self, stamp, rows, entry):
        # (unit, category) -> year -> summed value, within this one file
        totals = defaultdict(lambda: defaultdict(float))
        for row in rows:
            uid = unit_id(row) or government_id_key(row)
            kind = _lower(row.get('Production/Reserves'))
            if not uid:
                continue
            if kind != 'production':
                self.skipped_production[(_lower(row.get('Fuel Description')), _lower(row.get('Quantity Unit')), kind)] += 1
                continue
            quantity = parse_quantity(row.get('Quantity'))
            year = parse_quantity(row.get('Year'))
            converted = convert_production(row.get('Fuel Description'), quantity or 0.0, row.get('Quantity Unit'))
            if quantity is None or year is None or converted is None:
                self.skipped_production[(_lower(row.get('Fuel Description')), _lower(row.get('Quantity Unit')), kind)] += 1
                continue
            if quantity < 0:
                # a negative annual figure is a regulator's correction, not output
                self.skipped_production[(_lower(row.get('Fuel Description')), _lower(row.get('Quantity Unit')), 'negative quantity')] += 1
                continue
            category, value = converted
            totals[(uid, category)][int(year)] += value
        per_unit = defaultdict(dict)
        for (uid, category), by_year in totals.items():
            year = max(by_year)
            per_unit[uid][category] = (by_year[year], year)
        for uid, figures in per_unit.items():
            current = self.production.get(uid)
            if current is not None and current[0] > stamp:
                continue
            merged = dict(current[1]) if current else {}
            merged.update(figures)
            self.production[uid] = (stamp, merged)

    def _take_deletion(self, stamp, rows, entry):
        for row in rows:
            uid = unit_id(row)
            if uid:
                self.deleted[uid] = max(stamp, self.deleted.get(uid, stamp))

    def _take_new_asset(self, stamp, rows, entry):
        for row in rows:
            lat, lon = parse_quantity(row.get('Latitude')), parse_quantity(row.get('Longitude'))
            if _norm(row.get('Project Name')) and lat is not None and lon is not None:
                self.new_assets.append((stamp, row))

    # -- database lookups -----------------------------------------------------

    def entity_ids(self):
        ids = set()
        for _, entities in self.operator.values():
            ids.update(entities)
        for _, row in self.new_assets:
            entity = _norm(row.get('Operator GEM Entity ID'))
            if entity:
                ids.add(entity)
        return ids

    def resolve_companies(self):
        """Map the files' E-prefixed GEM entity ids to company names (one query)."""
        if self._company_names is not None:
            return self._company_names
        self._company_names = {}
        numeric = {}
        for entity in self.entity_ids():
            digits = entity[1:] if entity[:1].upper() == 'E' else entity
            if digits.isdigit():
                numeric[int(digits)] = entity
        if numeric:
            import gem_db
            rows = gem_db.fetch_all(
                'select id, name from company where id = any(:ids) and deleted is not true',
                {'ids': list(numeric)},
            )
            for company_id, name in rows:
                self._company_names[numeric[company_id]] = _norm(name)
        return self._company_names

    def operator_label(self, uid):
        """'; '-joined operator names for a unit, or None if the files say nothing.

        Entity ids the company table doesn't know are kept verbatim so the gap
        is visible on the map rather than silently dropped.
        """
        entry = self.operator.get(uid)
        if entry is None:
            return None
        names = self.resolve_companies()
        return '; '.join(names.get(entity, entity) for entity in entry[1])

    def db_timelines(self, uids):
        """Current database timelines for the given unit ids (for centroids)."""
        numeric = [int(u[1:]) for u in uids if u[:1] == 'L' and u[1:].isdigit()]
        if not numeric:
            return {}
        import gem_db
        rows = gem_db.fetch_all(
            """
            select 'L' || p.id,
                   json_agg(json_build_object(
                       'status', st.status, 'substatus', st.substatus,
                       'ord', st."order", 'year', st.year
                   ) order by st."order")
            from plant p
            join powerplant_unit u on u.plant_id = p.id
            join status_timeline st on st.unit_id = u.id
            where p.id = any(:ids)
            group by 1
            """,
            {'ids': numeric},
        )
        return {uid: timeline for uid, timeline in rows}

    # -- applying ------------------------------------------------------------

    def outline(self, uid, db_modified=None):
        """Bulk WKT for a unit unless the database outline was edited later."""
        entry = self.wkt.get(uid)
        if entry is None:
            return None
        if db_modified is not None and db_modified.replace(tzinfo=db_modified.tzinfo or timezone.utc) > entry[0]:
            return None
        return entry[1]

    def apply_status(self, props, uid, db_timeline):
        """Merge bulk timeline entries and refresh Status + the derived years."""
        entry = self.status.get(uid)
        if entry is None:
            return False
        props.update(timeline_props(merge_timeline(db_timeline, entry[1])))
        return True

    def apply_operator(self, props, uid):
        label = self.operator_label(uid)
        if label is None:
            return False
        props['Operator'] = label
        return True

    def apply_production(self, props, uid):
        entry = self.production.get(uid)
        if entry is None:
            return False
        figures = entry[1]
        if 'oil' in figures:
            props['ProdOil'] = round(figures['oil'][0], 3)
            props['ProdOilYear'] = str(figures['oil'][1])
        if 'gas' in figures:
            props['ProdGas'] = round(figures['gas'][0], 3)
            props['ProdGasYear'] = str(figures['gas'][1])
        props.update(capacity_from_production(props.get('ProdOil'), props.get('ProdGas')))
        return True

    def apply_latlon(self, feature, uid):
        """Move a centroid feature; outlines ignore point locations."""
        entry = self.latlon.get(uid)
        if entry is None or feature['geometry']['type'] != 'Point':
            return False
        _, lat, lon, accuracy, subnational = entry
        feature['geometry'] = {'type': 'Point', 'coordinates': [round(lon, 6), round(lat, 6)]}
        props = feature['properties']
        if accuracy:
            props['LocationAccuracy'] = accuracy
        if subnational:
            props['StartState/Province'] = subnational
            props['StartLocation'] = ', '.join(p for p in (subnational, props.get('CountriesOrAreas')) if p)
        return True

    def new_asset_features(self, template):
        """Centroid features for assets that don't have a GEM id yet.

        `template` is a dict of every handoff-schema property with its empty
        value, so the new features carry the same keys as the rest of the file.
        """
        names = self.resolve_companies()
        features = []
        for stamp, row in self.new_assets:
            props = dict(template)
            entity = _norm(row.get('Operator GEM Entity ID'))
            country = _norm(row.get('Country/Area'))
            subnational = _norm(row.get('Subnational Unit'))
            props.update({
                'PipelineName': _norm(row.get('Project Name')),
                'Status': NO_STATUS,
                'ProjectID': '',
                'CountriesOrAreas': country,
                'StartState/Province': subnational,
                'StartLocation': ', '.join(p for p in (subnational, country) if p),
                'Operator': names.get(entity, entity),
                'LocationAccuracy': _lower(row.get('Location accuracy')),
                'FuelType': _norm(row.get('GOGET Fuel Type')),
                'Tracker': 'GOGET',
            })
            key = government_id_key(row)
            if key:
                self.apply_production(props, key)
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [
                    round(parse_quantity(row.get('Longitude')), 6),
                    round(parse_quantity(row.get('Latitude')), 6)]},
                'properties': props,
            })
        return features

    # -- reporting -----------------------------------------------------------

    def describe(self):
        if self.empty and not self.ignored:
            return [f'no bulk uploads in {self.cache_dir} — run scripts/asana_goget_bulk_uploads.py first']
        lines = [f'bulk uploads from Asana ({self.cache_dir.name}): {len(self.files)} usable files, {len(self.ignored)} ignored']
        for entry in self.files:
            lines.append(f"  {entry['created_at'][:10]}  {entry['kind']:<10} {entry['rows']:>5} rows  {entry.get('parent_name') or entry.get('task_name')} / {entry['name']}")
        for entry in self.ignored:
            lines.append(f"  {entry['created_at'][:10]}  {'(ignored)':<10} {entry['rows']:>5} rows  {entry.get('parent_name') or entry.get('task_name')} / {entry['name']}")
        lines.append(
            f'  units with: outlines {len(self.wkt)}, locations {len(self.latlon)}, operators {len(self.operator)}, '
            f'status {len(self.status)}, production {len(self.production)}, deletions {len(self.deleted)}; '
            f'new assets {len(self.new_assets)}'
        )
        if self.skipped_production:
            lines.append('  production rows skipped (reserves, cumulative, or units the map cannot convert):')
            for (fuel, unit, kind), count in sorted(self.skipped_production.items(), key=lambda kv: -kv[1]):
                lines.append(f'    {count:>5}  {kind} / {fuel} / {unit}')
        return lines


if __name__ == '__main__':
    print('\n'.join(BulkOverlay.load(sys.argv[1] if len(sys.argv) > 1 else None).describe()))
