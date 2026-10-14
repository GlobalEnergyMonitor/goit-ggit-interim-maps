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
- https://globalenergymonitor.github.io/goit-ggit-interim-maps/trackers/goget/
- https://globalenergymonitor.github.io/goit-ggit-interim-maps/trackers/ggit-goget/
- https://globalenergymonitor.github.io/goit-ggit-interim-maps/trackers/ggit-goget-gogpt/

### When Pages can't deploy

Two independent things can block a deploy, so check which one it is:

- **The Actions deploy fails** (`Invalid actions OIDC token`, as in the
  2026-08-06 Actions/Pages outage). The workaround is to serve a branch instead
  of the Actions artifact — `node scripts/build-pages.mjs`, push `_dist/` to
  `gh-pages`, and set the repo's Pages source to that branch
  (`gh api -X PUT repos/.../pages` with `build_type=legacy`). The public URL
  doesn't change. **Switch it back to `build_type=workflow` afterwards**, or
  pushes to `main` will stop republishing the site.
- **Pages itself is down**, in which case neither path deploys. To get a map in
  front of someone anyway, `node scripts/build-standalone.mjs` writes a single
  self-contained HTML file per tracker into `_standalone/` (untracked). The
  Mapbox token is URL-restricted to `globalenergymonitor.github.io` and
  `localhost`, so those files must be *served*, not opened over `file://` —
  `cd _standalone && python3 -m http.server 8000`. Opening one directly loads
  the assets but no basemap (403 on tiles). The same restriction rules out
  hosting the maps anywhere else without editing the token's allowed URLs.

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
files under `trackers/ggit-goget/`. **The goget map** (`trackers/goget/`) shows those two GOGET files on their own, read from the same URLs, so it needs no data of its own.

- `goget_areas_latest.geojson` — field-outline polygons, read straight from the
  GEM project database (`project_geospatial.wkt`) by
  `scripts/build_goget_areas.py`, plus the outlines waiting in the open Asana
  bulk uploads (see below). The database is the only acceptable *release* source
  for these: it's fresher than the release sheet, and outlines longer than
  32,767 characters (Tupi, Cerro Dragon, most Dutch offshore fields) are
  truncated to unparseable WKT by Google Sheets' per-cell limit. Status comes
  from `status_timeline` (a timeline, not a scalar — `status_id` is null for
  every GOGET project), read the website's way (see below).
- `goget_map_latest.geojson` — centroid points for the fields that have no outline, read from the same database by `scripts/build_goget_map_data.py`, with the open bulk uploads' locations, deletions and new assets applied. Like the data team's export it replaced in October 2026, it includes only the projects flagged `goget_project.makeWIKI` (the export's own inclusion rule: every id in it carried the flag); the outline builder shows every traced outline regardless, which its `MAKE_WIKI_ONLY` constant can flip.

**Each field appears exactly once**, as an outline or a centroid, never both — the point builder drops the centroids of the fields the outline builder wrote. Keeping both would double-count them in the legend and the "total assets" line, because the shell groups features by link field *plus* coordinates and a polygon's coordinates never match its centroid's. So the two scripts must run **in that order**:

```
export GEM_READONLY_DB_URL=…      # read-only GEM project DB role
python3 scripts/build_goget_areas.py
python3 scripts/build_goget_map_data.py
```

Both read through `scripts/goget_db.py`. Since 2026-10-14 the project rows come from gem-db-ops' `export_goget_all_fields`, the port of the website's GOGET all-fields report, written to a temporary CSV (the same pattern as the GOGPT builder). Name, wiki link, location (including the subnational unit), outline, operators, status and the discovery, FID and production-start years are therefore the published spreadsheet's. Status is the latest non-`planned` timeline entry, so a field with only planned entries shows `not found`. Production start year is the first dated `operating` + `ramp up` entry, so a field whose only operating entry is an as-of year has no start year. `ProjectID` is the export's `Unit ID`, the plant id with an `L` prefix, which is also what the Asana bulk uploads use (the old query took `unitIDSearch[1]`, the unit id, which differs for about 1,050 fields and kept those out of the overlay). A small extra query adds what the export lacks: the second country, the raw timeline the bulk overlay merges into, the outline's modified date, and the owners with their shares as recorded (the export truncates shares to whole numbers, so a 0.74% stake reads `[0%]`; the map keeps the decimals). Two more columns are derived here because the export has no equivalent:

- Production and capacity come from `reserves_production` rows of kind `production`, converted by `goget_bulk_overlay.convert_production` (the same code the bulk-upload overlay uses): oil and condensate in bbl, m³ or tonnes (7.33 bbl/tonne) to million bbl/y, gas in m³ or cubic feet (standard/normal variants, bcm, mcf/mmcf/bcf) to million m³/y, latest year per fuel, summed within that year. `Capacity` is oil + gas / 169.9813 m³ per boe in million boe/y, `CapacityBOEd` the same as boe/d. Checked against the March 2026 export: within rounding on about 3,150 of 3,350 projects per fuel, the rest updated in the database since. NGL, LPG, boe and energy units are skipped and listed in the build log, never guessed; add a unit to `UNIT_RE` or a fuel to `OIL_FUELS`/`GAS_FUELS` there to cover more.
- Parent comes from the owner companies' precomputed ultimate parents (`company.gemParentsJSON`): owner share × chain share summed per parent, one decimal, biggest first, and an owner with no recorded share lists its parents without a bracket. 5,927 of the export's 7,673 strings reproduced exactly; the rest are mostly company renames since March.

All four database-reading builders (`build_goget_areas.py`, `build_goget_map_data.py`, `build_gogpt_map_data.py`, `build_lng_map_data.py`) get their connection from the sibling **`gem-db-ops`** repo through `scripts/gem_db.py` — that repo is the single source of truth for GEM data access, so the read-only session guard and statement timeout come along for free. Clone it beside this one, or point `GEM_DB_OPS_REPO` at it. Don't add a local `psycopg2.connect` back (the pre-2026-08-11 shape); extend `scripts/gem_db.py` instead.

Then commit and push the regenerated files (or let the workflow below do it).

### The GOGET bulk uploads waiting in Asana

The GOGET researchers hand their updates to the data team as **bulk-upload requests** in the Asana "Data team inbox" project (mostly in its "Bulk Upload Requests" section, though older ones sit in "Tracker Releases"; one task per region: Alberta, Saskatchewan, British Columbia, Australia, Texas, the UK, Argentina, Brazil, …), with the CSVs attached to the task's subtasks or to the task itself. Until the data team processes a request its data is in neither the database nor the export, yet it is the freshest GOGET data there is: new field outlines (WKT), moved centroids, production, operators, statuses and deletions. So both GOGET builders overlay those files on top of what they read. The requests belong to the data team: nothing here completes, edits or comments on them, and the downloader only ever sends GET requests.

- `scripts/asana_goget_bulk_uploads.py` downloads every `.csv` attached to an **incomplete** GOGET bulk-upload task anywhere in that project (Tracker custom field or name says GOGET; Task Type, Data Product or Project, or name says bulk upload) or to one of its incomplete subtasks, into the gitignored `_asana_cache/` (`files/<attachment gid>.csv` plus `manifest.json`). Completed subtasks are skipped because that data is already in the database, and a request that has since been completed drops out of the cache on the next run. It needs an Asana personal access token in `ASANA_ACCESS_TOKEN` (https://app.asana.com/0/my-apps, any workspace member who can see the inbox; locally, `~/.config/asana/token` holds one).
- `scripts/goget_bulk_overlay.py` reads that cache. It classifies each CSV by its header (outline WKT, lat/lon, new assets, production, operator, status/timeline, deletion; reserves, other IDs and record-of-updates files are ignored), and when the same unit is in several files the newest upload wins. A file that still has the upload template's title and instruction lines above its header is read from the first line it recognizes. Running it on its own prints what it found.
- `data/goget_bulk_static/` holds bulk files that Asana links as Google Sheets instead of attaching as CSVs, which the downloader can't fetch (CI has no Google login). Each was exported by hand with `gws-gem` into `files/` and listed in its own `manifest.json` (same format as the cache's, plus a `source` link); the overlay reads it together with `_asana_cache/`. It now holds the Texas new-assets production sheet. Its rows have no GEM ID, only a temporary government unit ID, so production rows without an ID are keyed on that column and the new-asset points pick them up by it. Re-export a file if its sheet changes, and delete it once its Asana task is complete.
- `build_goget_areas.py` draws a bulk outline for any GOGET project that has one, unless the database outline was modified after the upload; a field with a bulk outline that does not parse keeps its database outline. `build_goget_map_data.py` moves centroids, drops deleted units, and appends the Texas "new assets" (fields with no GEM ID yet) as points with an empty `ProjectID` and `Wiki`. Both apply operators (`E…` IDs resolved through the `company` table), statuses (appended to the database timeline, then read with the export's own rules through `timeline_props`) and production.
- Production: only `Production/Reserves == production` rows are used, converted with the same `convert_production` the database builders use (oil and condensate in bbl, m³ or tonnes; gas in m³ or cubic feet; see above), summed for the latest year per fuel, and `Capacity` recomputed the same way. LPG, NGL, reserves, cumulative production, energy units and negative (correction) rows are skipped and listed in the run summary.

The daily `build map data` workflow (`.github/workflows/build-map-data.yml`, 06:41 UTC, also `gh workflow run build-map-data.yml`) runs the downloader and then all four builders — GOGET outlines, GOGET centroids, GOGPT units, LNG terminals — fresh from the database on every run, and commits whichever of the four geojsons changed. It needs two repo secrets: `ASANA_ACCESS_TOKEN` and `GEM_READONLY_DB_URL` (the database must accept connections from GitHub runners). Locally, run the downloader first and the GOGET builders pick the cache up automatically; without a cache they build from the database alone.

**The ggit-goget-gogpt map** is the ggit-goget map with two more sources: GOGPT
oil & gas power plants and GGIT LNG terminals. It reads the GGIT pipelines file
and *the same two GOGET files from `trackers/ggit-goget/`* — they aren't copied,
so regenerating them updates both maps — plus two committed files of its own:

- `trackers/ggit-goget-gogpt/gogpt_map_latest.geojson` — plant points, one feature per generating unit, read from the GEM project database by `scripts/build_gogpt_map_data.py` (needs `GEM_READONLY_DB_URL` and the gem-db-ops checkout). It runs gem-db-ops' `export_gogpt_all_fields` — the code behind the published GOGPT all-fields spreadsheet, so owners, parents, status and technology are spelled the way the published data spells them — into a temporary CSV and keeps the units whose `powerplant_unit.trackerSearch` is `GOGPT`, have coordinates and have a status (inferred statuses such as `shelved - inferred 2 y` are shortened to `shelved`). Until October 2026 this renamed the data team's CDN export instead. Nothing is de-duplicated against GOGET — plants and extraction areas are separate assets — so this script has no required run order.
- `trackers/ggit-goget-gogpt/lng_map_latest.geojson` — LNG terminal points, one
  feature per terminal unit, read straight from the GEM project database by
  `scripts/build_lng_map_data.py` (needs `GEM_READONLY_DB_URL`). There is no
  published LNG map export to rename, and the DB is what the researchers work
  in. `gem-db-ops/lng/pull.py` exports the same tracker as the website's
  115-column all-fields CSV; this builder pulls only the columns the map draws,
  so the two don't have to stay in step. Terminals with no coordinates in the DB
  (a handful) are skipped and listed in the output. **The LNG terminals are only
  on this map** — the ggit map stays gas pipelines only.

Units aren't merged: the shell groups features sharing link field + coordinates,
so a station's or terminal's units render as one marker (a pie chart when their
statuses differ) and the detail card lists them individually. The legend counts,
like the pipeline sections' segment counts, are per unit.

The legend has one section per tracker, which works via the shell's
`derivedFields` config: `Status` is copied into `PipelineStatus` on the lines,
`ExtractionStatus` on the GOGET outlines and points, and (on the four-tracker
map) `PlantStatus` on the GOGPT units and `TerminalStatus` on the LNG units, and
a filter section ignores features that don't carry its field, so each section
filters only its own tracker while the map paint still colors off the single
shared `Status`. A `derivedFields` rule selects features by `geometries`, by
`where: {field, value}`, or both — `where` is what separates the GOGET centroids
from the GOGPT plants and LNG terminals, since geometry alone can't (all three
are points).

On both combined maps each of those sections is a **collapsible asset accordion**:
a caret expands its status rows, and a switch on the header — visible whether the
section is open or closed — turns that whole asset on or off (it replaces the
per-section "select all section / clear all section" links; the legend-wide
select all / clear all stays). The switch shows a half-way state when only some
of a section's statuses are ticked. `collapsibleSections: true` in the tracker
config turns this on, and each filter takes `startExpanded` / `startOn`
(both default true). Both maps load with only **Gas pipelines** expanded and
drawn; the other assets start collapsed and switched off, which `enableUX()`
applies with one filter pass once the geojson source has finished loading —
a `setData()` issued before that is silently dropped, so the map would keep
drawing everything while the legend claimed otherwise.

Because all those points share one status palette, **shape carries the tracker**
on that map: power plants are squares, LNG terminals triangles, extraction-area
centroids circles. That's `markerShapes: [{field, value, shape}]` in the tracker
config, with `dotShape` on the matching legend section. Mapbox circle layers can
only draw circles, so a shaped marker is a generated canvas image (the same
status pie, clipped to the shape) drawn through the symbol layer — see
`MARKER_CLIP_PATHS` in `src/site.js`, which is also where a new shape would be
added.

**Shaped markers are all one size**: capacity scaling only makes sense between
things measured the same way, and plant capacity is nameplate MW while LNG
capacity is whatever unit each terminal recorded, so the squares and triangles
are drawn at a fixed radius (`shapeMarkerRadius` / `highZoomShapeMarkerRadius` in
`site-config.js`, growing with zoom like everything else) and are left out of the
capacity range in `setMinMax()`. Pipelines and the GOGET extraction centroids —
both boe/d — keep scaling against each other. Radius still comes from one field,
`CapacityMapScale`, which `derivedFields` fills from `CapacityBOEd` for those two
sources; the GOGPT builder's own value (MW × 100, display-only) and the LNG
builder's (boe/d, LNG via ~23,300 boe/d per Mtpa, unconvertible units left
unscaled) are now carried but unused for size. Real figures stay in
`Capacity`/`CapacityUnits`, which is what the detail card, the table and the
downloads report.

## Copying coordinates

Every map offers a location two ways: **right-click anywhere** for a
"copy coordinates" menu with the point under the cursor, and, for assets that are
a single point in space (power plants, LNG terminals, extraction-area centroids),
a **Coordinates** row under Status in the click-through detail card. Both give
`lat, lon` at 5 decimal places and copy to the clipboard. Pipelines and field
outlines have no single coordinate, so they get no row.

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
# → http://localhost:8080/maps/trackers/goget/
# → http://localhost:8080/maps/trackers/ggit-goget/
# → http://localhost:8080/maps/trackers/ggit-goget-gogpt/
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
- `.github/workflows/build-map-data.yml` — daily rebuild of the GOGET, GOGPT and LNG files from the database (plus the open Asana bulk uploads for GOGET)
- `_asana_cache/` (gitignored) — the downloaded bulk-upload CSVs and their manifest
- `data/goget_bulk_static/` — bulk-upload Google Sheets exported by hand for the overlay (see the GOGET section)
