import { promises as fs } from "node:fs";
import path from "node:path";

const DIST = path.resolve("_dist");

async function ensureDir(dir) {
    await fs.mkdir(dir, { recursive: true });
}

async function exists(p) {
    try {
        await fs.access(p);
        return true;
    } catch {
        return false;
    }
}

async function copyFile(src, dst) {
    await ensureDir(path.dirname(dst));
    await fs.copyFile(src, dst);
}

async function copyDir(srcDir, dstDir) {
    await ensureDir(dstDir);
    const entries = await fs.readdir(srcDir, { withFileTypes: true });

    for (const entry of entries) {
        const srcPath = path.join(srcDir, entry.name);
        const dstPath = path.join(dstDir, entry.name);

        if (entry.isDirectory()) {
            await copyDir(srcPath, dstPath);
        } else if (entry.isFile()) {
            await fs.copyFile(srcPath, dstPath);
        }
    }
}

async function main() {
    const SRC_DIR = path.resolve("src");
    const TRACKERS_DIR = path.resolve("trackers");
    const SITE_CONFIG = path.resolve("site-config.js");
    const PACKAGES_DIR = path.resolve("packages");
    const TRACKERS_INDEX = path.join(TRACKERS_DIR, "index.html");

    const SRC_INDEX = path.join(SRC_DIR, "index.html");

    if (!(await exists(SRC_INDEX))) {
        throw new Error("Missing src/index.html");
    }

    if (!(await exists(TRACKERS_DIR))) {
        throw new Error("Missing trackers/ directory");
    }

    // Clean _dist
    await fs.rm(DIST, { recursive: true, force: true });
    await ensureDir(DIST);

    console.log("Building Pages output...");

    // 1. Copy entire src/ directory unchanged
    console.log("Copying src/ → _dist/src/");
    await copyDir(SRC_DIR, path.join(DIST, "src"));

    // 1b. Copy entire packages/ directory unchanged (if present)
    if (await exists(PACKAGES_DIR)) {
        console.log("Copying packages/ → _dist/packages/");
        await copyDir(PACKAGES_DIR, path.join(DIST, "packages"));
    }

    // 2. Copy site-config.js if present
    if (await exists(SITE_CONFIG)) {
        console.log("Copying site-config.js");
        await copyFile(SITE_CONFIG, path.join(DIST, "site-config.js"));
    }

    // 3. Optional: publish a root index.html (same as src/index.html)
    console.log("Publishing root index.html");
    await copyFile(SRC_INDEX, path.join(DIST, "index.html"));

    // 3b. Publish trackers index if present
    if (await exists(TRACKERS_INDEX)) {
        console.log("Publishing trackers/index.html");
        await copyFile(TRACKERS_INDEX, path.join(DIST, "trackers", "index.html"));
    }

    // 4. Build tracker pages
    const trackerFolders = await fs.readdir(TRACKERS_DIR, { withFileTypes: true });

    for (const entry of trackerFolders) {
        if (!entry.isDirectory()) continue;

        const trackerName = entry.name;
        const trackerConfig = path.join(TRACKERS_DIR, trackerName, "config.js");

        // Skip folders without config.js
        if (!(await exists(trackerConfig))) continue;

        const outTrackerDir = path.join(DIST, "trackers", trackerName);
        await ensureDir(outTrackerDir);

        console.log(`Generating tracker page: ${trackerName}`);

        // Copy canonical index.html into tracker folder
        await copyFile(SRC_INDEX, path.join(outTrackerDir, "index.html"));

        // Copy tracker config
        await copyFile(trackerConfig, path.join(outTrackerDir, "config.js"));

        // Conditionally copy countries.json if it exists
        const countriesFile = path.join(TRACKERS_DIR, trackerName, "countries.json");
        if (await exists(countriesFile)) {
            await copyFile(countriesFile, path.join(outTrackerDir, "countries.json"));
        }
    }

    console.log("Build complete → _dist/");
}

main().catch((err) => {
    console.error("Build failed:");
    console.error(err);
    process.exit(1);
});
