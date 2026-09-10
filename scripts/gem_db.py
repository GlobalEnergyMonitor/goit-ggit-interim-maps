#!/usr/bin/env python3
"""GEM project-database access for the build scripts — borrowed, not reinvented.

The connection details (env var, `postgres://` -> `postgresql://` fixup, the
read-only session guard, the statement timeout) live in ONE place across all the
GEM repos: the sibling `gem-db-ops` checkout. This module resolves that checkout
and re-exports what the builders need, so a fix there fixes this repo too.

Before 2026-08-11 build_lng_map_data.py and build_goget_areas.py each called
`psycopg2.connect(os.environ['GEM_READONLY_DB_URL'])` directly, which worked but
skipped the `default_transaction_read_only=on` guard — the thing that makes an
accidental write impossible rather than merely unlikely. Don't go back to a bare
connect; add what you need here.

Layout assumption: gem-db-ops sits beside this repo. Override with
GEM_DB_OPS_REPO=/path/to/gem-db-ops.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_VAR = 'GEM_DB_OPS_REPO'


def db_ops_repo() -> Path:
    """Path to the gem-db-ops checkout that owns the pull/query engine."""
    override = os.environ.get(ENV_VAR)
    candidate = Path(override).expanduser() if override else REPO_ROOT.parent / 'gem-db-ops'
    if not (candidate / 'gem_query.py').is_file():
        sys.exit(
            f'gem-db-ops not found at {candidate}\n'
            f'Clone it beside this repo, or set {ENV_VAR}=/path/to/gem-db-ops.\n'
            'It owns the GEM database connection + every tracker pull.'
        )
    return candidate


def build_readonly_engine():
    """SQLAlchemy Engine whose every session is read-only, from gem-db-ops."""
    path = str(db_ops_repo())
    if path not in sys.path:
        sys.path.insert(0, path)
    from gem_query import (  # noqa: E402
        DEFAULT_STATEMENT_TIMEOUT_MS,
        build_engine,
        get_database_url,
    )

    return build_engine(get_database_url(), DEFAULT_STATEMENT_TIMEOUT_MS)


def fetch_all(query: str, params: dict | None = None) -> list[tuple]:
    """Run a SELECT against the read-only GEM database; return rows as tuples."""
    from sqlalchemy import text  # imported here so the module stays cheap

    engine = build_readonly_engine()
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(text(query), params or {})]
