/* Build a single self-contained HTML file per tracker into _standalone/.

   Everything from this repo is inlined (site.css, site.js, site-config.js, the tracker
   config, bootstrap, jquery-csv, and the svg icons as data URIs); the third-party CDN
   tags are left as-is. The geojson is still fetched from raw.githubusercontent at
   runtime, so a bundle stays current as the data rebuilds.

   This is the escape hatch for when Pages can't deploy (see README) — hand someone one
   file instead of a URL. NOTE: the Mapbox token is URL-restricted to
   globalenergymonitor.github.io and localhost, so opening the file directly over
   file:// renders the assets but no basemap (403 on tiles). It has to be served over
   localhost:

       cd _standalone && python3 -m http.server 8000
       open http://localhost:8000/gem-map-ggit-goget.html

   Usage: node scripts/build-standalone.mjs [tracker ...]   (default: all trackers)
*/
import { promises as fs } from 'node:fs';
import path from 'node:path';

const REPO = path.resolve(import.meta.dirname, '..');
const OUT_DIR = path.join(REPO, '_standalone');

const read = (p) => fs.readFile(path.join(REPO, p), 'utf8');

async function exists(p) {
    try {
        await fs.access(path.join(REPO, p));
        return true;
    } catch {
        return false;
    }
}

async function build(tracker) {
    let html = await read('src/index.html');

    /* String.replace() interprets $-patterns in a string replacement, and the inlined
       jquery source is full of them — hence the function replacements throughout. */
    for (const [tag, file] of [
        ['<link href="../../packages/bootstrap-lux/bootstrap.min.css" rel="stylesheet" />', 'packages/bootstrap-lux/bootstrap.min.css'],
        ['<link href="../../src/site.css" id="site-style" rel="stylesheet" />', 'src/site.css'],
    ]) {
        const css = await read(file);
        html = html.replace(tag, () => '<style>\n' + css + '\n</style>');
    }

    for (const [tag, file] of [
        ['<script src="../../packages/jquery-csv.js"></script>', 'packages/jquery-csv.js'],
        ['<script src="../../site-config.js"></script>', 'site-config.js'],
        ['<script src="./config.js"></script>', `trackers/${tracker}/config.js`],
        ['<script src="../../src/site.js"></script>', 'src/site.js'],
    ]) {
        const js = await read(file);
        html = html.replace(tag, () => '<script>\n' + js + '\n</script>');
    }

    for (const name of await fs.readdir(path.join(REPO, 'src/img'))) {
        if (!name.endsWith('.svg')) continue;
        const uri = 'data:image/svg+xml;base64,' + Buffer.from(await read(`src/img/${name}`)).toString('base64');
        html = html.split(`../../src/img/${name}`).join(uri);  // html attributes
        html = html.split(`./img/${name}`).join(uri);           // site.css url() refs
    }

    // countries.json is fetched by relative path, which no longer resolves once flattened
    html = html.split("'../../src/countries.json'").join(
        "'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/src/countries.json'");

    const leftovers = [
        ...[...html.matchAll(/(?:src|href)="\.\.?\/[^"]*"/g)].map((m) => m[0]),
        ...[...html.matchAll(/url\(\.?\.?\/?img\/[^)]*\)/g)].map((m) => m[0]),
    ];
    if (leftovers.length) throw new Error(`${tracker}: un-inlined local refs: ${leftovers.join(', ')}`);

    html = html.replace('<title></title>', `<title>GEM interim map — ${tracker}</title>`);

    const out = path.join(OUT_DIR, `gem-map-${tracker}.html`);
    await fs.writeFile(out, html);
    console.log(`${tracker} → ${path.relative(REPO, out)}  ${(html.length / 1024).toFixed(0)} KB`);
}

const requested = process.argv.slice(2);
const trackers = requested.length
    ? requested
    : (await fs.readdir(path.join(REPO, 'trackers'), { withFileTypes: true }))
        .filter((e) => e.isDirectory())
        .map((e) => e.name);

await fs.mkdir(OUT_DIR, { recursive: true });
for (const tracker of trackers) {
    if (!(await exists(`trackers/${tracker}/config.js`))) {
        console.log(`skipping ${tracker} (no config.js)`);
        continue;
    }
    await build(tracker);
}
