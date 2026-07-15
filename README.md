# goit-ggit-cycle-maps

Test maps for the GOIT/GGIT annual update cycles, so researchers can view
in-progress pipeline data on a map without waiting for the data team's annual
sync of the official trackers.

Snapshot of the map app shell from
[interim-maps](https://github.com/GlobalEnergyMonitor/interim-maps)
(July 2026), trimmed to the two pipeline trackers.

## Live maps

Deployed to GitHub Pages on every push to `main`:

- https://globalenergymonitor.github.io/goit-ggit-cycle-maps/trackers/goit/
- https://globalenergymonitor.github.io/goit-ggit-cycle-maps/trackers/ggit/

## Updating the data a map shows

Each map loads its data at runtime from the `geojson:` URL at the top of
`trackers/<name>/config.js`. To point a map at new data, change that URL and
push. The data file must expose the property names the config references
(see the existing files on the CDN for the schema).

**The GOIT map updates itself.** Its config points at the raw URL of the
single-commit `map-data` branch of
[goit-ggit-data-ops](https://github.com/GlobalEnergyMonitor/goit-ggit-data-ops),
which that repo's `build map data` workflow rebuilds and force-pushes whenever
[goit-ggit-pipeline-routes](https://github.com/GlobalEnergyMonitor/goit-ggit-pipeline-routes)
updates its `normalized` branch (plus a daily cron for sheet-only edits). The
file uses the data-team handoff schema (`PipelineName`, `Status`, `Wiki`,
`CapacityBOEd`, …) with null-geometry rows dropped; no commit here is needed
for data refreshes (raw.githubusercontent.com caches for ≤5 min and sends
CORS headers). The GGIT map is still pointed at a manually uploaded snapshot
on DO Spaces.

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
```

## Layout

- `src/` — shared app shell (Mapbox GL map, table, filters, detail cards)
- `site-config.js` — sitewide defaults (token, style, colors, field names)
- `trackers/<name>/config.js` — per-map config; overrides site-config
- `scripts/build-pages.mjs` — assembles `_dist/` for Pages; auto-includes any
  `trackers/*/config.js` folder, so adding a new map is just a new folder
- `.github/workflows/pages.yml` — deploys `_dist/` to Pages on push to `main`
