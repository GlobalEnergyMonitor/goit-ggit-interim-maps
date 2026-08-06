# goit-ggit-interim-maps

Test maps for the GOIT/GGIT annual update cycles, so researchers can view
in-progress pipeline data on a map without waiting for the data team's annual
sync of the official trackers.

Snapshot of the map app shell from
[interim-maps](https://github.com/GlobalEnergyMonitor/interim-maps)
(July 2026), trimmed to the two pipeline trackers.

## Live maps

Deployed to GitHub Pages on every push to `main`:

- https://globalenergymonitor.github.io/goit-ggit-interim-maps/trackers/goit/
- https://globalenergymonitor.github.io/goit-ggit-interim-maps/trackers/ggit/
- https://globalenergymonitor.github.io/goit-ggit-interim-maps/trackers/ggit-goget/

## Updating the data a map shows

Each map loads its data at runtime from the `geojson:` URL at the top of
`trackers/<name>/config.js`. To point a map at new data, change that URL and
push. The data file must expose the property names the config references
(see the existing files on the CDN for the schema).

**The GOIT and GGIT maps update themselves.** Each config points at a raw URL
on the single-commit `map-data` branch of
[goit-ggit-data-ops](https://github.com/GlobalEnergyMonitor/goit-ggit-data-ops)
(`goit_map_latest.geojson` / `ggit_map_latest.geojson`), which that repo's
`build map data` workflow rebuilds and force-pushes whenever
[goit-ggit-pipeline-routes](https://github.com/GlobalEnergyMonitor/goit-ggit-pipeline-routes)
updates its `normalized` branch (plus a daily cron for sheet-only edits). The
files use the data-team handoff schema (`PipelineName`, `Status`, `Wiki`,
`CapacityBOEd`, …) with null-geometry rows dropped; no commit here is needed
for data refreshes (raw.githubusercontent.com caches for ≤5 min and sends
CORS headers). The GGIT map shows gas pipelines only — LNG terminals will get
their own map separately.

**The ggit-goget map** overlays GOGET oil & gas extraction areas on the GGIT
pipelines. Its `geojson:` key is an *array* of URLs (the shared shell merges
multiple sources): the same auto-updating GGIT file, plus two committed GOGET
files under `trackers/ggit-goget/`.

- `goget_areas_latest.geojson` — field-outline polygons, read straight from the
  GEM project database (`project_geospatial.wkt`) by
  `scripts/build_goget_areas.py`. The database is the only acceptable source
  for these: it's fresher than the release sheet, and outlines longer than
  32,767 characters (Tupi, Cerro Dragon, most Dutch offshore fields) are
  truncated to unparseable WKT by Google Sheets' per-cell limit. Status comes
  from `status_timeline` (a timeline, not a scalar — `status_id` is null for
  every GOGET project), taking the highest-`order` entry that isn't a
  `planned` substatus.
- `goget_map_latest.geojson` — centroid points for the fields that have no
  outline, from the data team's export
  (`publicgemdata…/interim_maps/goget_map_*.geojson`) with properties renamed
  to the handoff schema, by `scripts/build_goget_map_data.py`.

**Each field appears exactly once**, as an outline or a centroid, never both —
the outline builder copies the export's production, capacity and parent values
onto the matching outline, and the point builder then drops those fields'
centroids. Keeping both would double-count them in the legend and the "total
assets" line, because the shell groups features by link field *plus*
coordinates and a polygon's coordinates never match its centroid's. So the
two scripts must run **in that order**, and the outline builder reads the
published export rather than the local points file (which no longer has those
rows):

```
export GEM_READONLY_DB_URL=…      # read-only GEM project DB role
python3 scripts/build_goget_areas.py
python3 scripts/build_goget_map_data.py
```

Then commit and push both regenerated files. Update `SOURCE_URL` in
`build_goget_map_data.py` first if the data team published a newer export.
Production/capacity and Parent are deliberately *not* derived from the database
— production lives in `reserves_production` in ~110 fuel-description × unit
combinations (including mass and energy units needing density/heat-content
assumptions), and Parent needs a real ownership-tree traversal; both are the
data team's and the ownership repos' normalization to own.

The legend has one section per tracker, which works via the shell's
`derivedFields` config: `Status` is copied into `PipelineStatus` on the lines
and `ExtractionStatus` on the outlines and points, and a filter section ignores
features that don't carry its field, so each section filters only its own
tracker while the map paint still colors off the single shared `Status`.

Data files larger than 100 MB cannot be committed to this repo (GitHub limit) —
host those on DigitalOcean Spaces (needs CORS open, as `publicgemdata` already
is). Smaller subset files can be committed and referenced by relative path.

Note: this repo, its Pages site, and the CDN data are all public. Don't point
a map at data that shouldn't be public yet unless "unlisted but public" is
acceptable.

## Run locally

```
python server.py
# → http://localhost:8080/maps/trackers/goit/
# → http://localhost:8080/maps/trackers/ggit/
# → http://localhost:8080/maps/trackers/ggit-goget/
```

Data loads from the committed `raw.githubusercontent.com` URLs even when running
locally, so a regenerated geojson only shows up after it's pushed.

## Layout

- `src/` — shared app shell (Mapbox GL map, table, filters, detail cards)
- `site-config.js` — sitewide defaults (token, style, colors, field names)
- `trackers/<name>/config.js` — per-map config; overrides site-config
- `scripts/build-pages.mjs` — assembles `_dist/` for Pages; auto-includes any
  `trackers/*/config.js` folder, so adding a new map is just a new folder
- `.github/workflows/pages.yml` — deploys `_dist/` to Pages on push to `main`
