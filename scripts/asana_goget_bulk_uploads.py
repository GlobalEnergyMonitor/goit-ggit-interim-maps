#!/usr/bin/env python3
"""Download the CSVs of every open GOGET bulk-upload request from Asana.

The GOGET researchers hand their updates (field outlines, locations, production,
operators, status, deletions) to the data team as bulk-upload requests in the
Asana "Data team inbox" project (mostly in its "Bulk Upload Requests" section,
but older ones sit in "Tracker Releases"): one task per region, with the CSV
files attached to its subtasks (sometimes to the task itself). Until the data team processes a request its data isn't in the GEM
database, so the map builders overlay these files on top of the database
(see scripts/goget_bulk_overlay.py). This script fills the cache they read.

Strictly read-only: it only ever sends GET requests. The requests belong to the
data team — nothing here completes, edits, comments on or reassigns them.

Selection: incomplete tasks anywhere in that project whose "Tracker" custom
field says GOGET and that are bulk uploads (by name, "Task Type" or "Data
Product or Project"), plus every incomplete subtask of those. Subtasks the data team has already completed are
skipped — that data is in the database already. Only .csv attachments with a
download URL are fetched (Asana also records files that live elsewhere, with
no download URL).

Needs an Asana personal access token in ASANA_ACCESS_TOKEN
(https://app.asana.com/0/my-apps → "Create new token"; a token of any member
of the GEM workspace who can see the Data team inbox works):

    export ASANA_ACCESS_TOKEN=…
    python3 scripts/asana_goget_bulk_uploads.py            # -> _asana_cache/
    python3 scripts/asana_goget_bulk_uploads.py --cache-dir /elsewhere

The cache holds files/<attachment gid>.csv plus manifest.json (attachment,
subtask and parent task names, upload dates, paths). Files whose request has
since been completed or whose attachment is gone are removed from the cache, so
a processed request stops being overlaid on the next run. Already-downloaded
attachments aren't fetched again (attachments are immutable in Asana; a new
upload is a new gid).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goget_bulk_overlay import DEFAULT_CACHE_DIR, MANIFEST_NAME  # noqa: E402

API = 'https://app.asana.com/api/1.0'
TOKEN_ENV_VAR = 'ASANA_ACCESS_TOKEN'

DATA_TEAM_INBOX_PROJECT = '1204455496936499'
TRACKER_FIELD = 'Tracker'                  # custom field, e.g. "GOGET (Gas & Oil extraction)"
TASK_TYPE_FIELDS = ('Task Type', 'Data Product or Project')   # either may say "Bulk upload"

TASK_FIELDS = 'name,completed,created_at,parent.gid,custom_fields.name,custom_fields.display_value'
ATTACHMENT_FIELDS = 'name,created_at,download_url,resource_subtype'


class Asana:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers['Authorization'] = f'Bearer {token}'
        self.session.headers['Accept'] = 'application/json'

    def get(self, path, **params):
        """GET with pagination and a polite retry on rate limiting."""
        params.setdefault('limit', 100)
        items = []
        while True:
            for attempt in range(5):
                response = self.session.get(f'{API}{path}', params=params, timeout=60)
                if response.status_code == 429:
                    time.sleep(int(response.headers.get('Retry-After', '5')) + 1)
                    continue
                break
            response.raise_for_status()
            body = response.json()
            data = body['data']
            if isinstance(data, list):
                items.extend(data)
            else:
                return data
            next_page = body.get('next_page')
            if not next_page:
                return items
            params['offset'] = next_page['offset']


def custom_field(task, name):
    for field in task.get('custom_fields') or []:
        if field.get('name') == name:
            return field.get('display_value') or ''
    return ''


def is_goget_bulk_upload(task):
    name = (task.get('name') or '').lower()
    tracker = custom_field(task, TRACKER_FIELD).lower()
    task_types = [custom_field(task, field).lower() for field in TASK_TYPE_FIELDS]
    is_goget = 'goget' in tracker or 'goget' in name
    is_bulk = 'bulk upload' in name or any('bulk upload' in t for t in task_types)
    return is_goget and is_bulk


def open_requests(asana):
    """Top-level open GOGET bulk-upload tasks in the inbox, oldest first."""
    tasks = asana.get(f'/projects/{DATA_TEAM_INBOX_PROJECT}/tasks',
                      completed_since='now', opt_fields=TASK_FIELDS)
    chosen = {t['gid']: t for t in tasks if not t.get('completed') and is_goget_bulk_upload(t)}
    # a subtask that was also added to the project shows up on its own — keep
    # it only through its parent, so each file is listed once
    for gid in list(chosen):
        parent = (chosen[gid].get('parent') or {}).get('gid')
        if parent in chosen:
            del chosen[gid]
    return sorted(chosen.values(), key=lambda t: t['created_at'])


def csv_attachments(asana, task):
    attachments = asana.get('/attachments', parent=task['gid'], opt_fields=ATTACHMENT_FIELDS)
    return [a for a in attachments
            if (a.get('name') or '').lower().endswith('.csv') and a.get('download_url')]


def collect(asana):
    """Manifest entries for every CSV on the open requests and their subtasks."""
    entries = []
    for task in open_requests(asana):
        holders = [(task, None)]
        subtasks = asana.get(f'/tasks/{task["gid"]}/subtasks', opt_fields=TASK_FIELDS)
        holders += [(sub, task) for sub in subtasks if not sub.get('completed')]
        for holder, parent in holders:
            for attachment in csv_attachments(asana, holder):
                entries.append({
                    'gid': attachment['gid'],
                    'name': attachment['name'],
                    'created_at': attachment['created_at'],
                    'download_url': attachment['download_url'],
                    'task_gid': holder['gid'],
                    'task_name': holder['name'],
                    'parent_gid': (parent or holder)['gid'],
                    'parent_name': (parent or holder)['name'],
                    'path': f'files/{attachment["gid"]}.csv',
                })
    return entries


def download(session, entries, cache_dir):
    files_dir = cache_dir / 'files'
    files_dir.mkdir(parents=True, exist_ok=True)
    fetched = 0
    for entry in entries:
        target = cache_dir / entry['path']
        if target.is_file() and target.stat().st_size > 0:
            continue
        # download URLs are signed and short-lived, so fetch them right away
        response = session.get(entry['download_url'], timeout=300)
        response.raise_for_status()
        target.write_bytes(response.content)
        fetched += 1
    keep = {cache_dir / e['path'] for e in entries}
    removed = 0
    for stale in files_dir.glob('*.csv'):
        if stale not in keep:
            stale.unlink()
            removed += 1
    return fetched, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--cache-dir', type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        sys.exit(f'{TOKEN_ENV_VAR} is not set — create a personal access token at '
                 'https://app.asana.com/0/my-apps and export it (never commit it).')

    asana = Asana(token)
    entries = collect(asana)
    fetched, removed = download(asana.session, entries, args.cache_dir)

    # the signed URLs expire within hours; don't keep them around
    manifest = [{k: v for k, v in e.items() if k != 'download_url'} for e in entries]
    (args.cache_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=1))

    by_request = {}
    for entry in manifest:
        by_request.setdefault(entry['parent_name'], []).append(entry)
    print(f'{len(by_request)} open GOGET bulk-upload requests, {len(manifest)} csv files '
          f'({fetched} downloaded, {removed} stale files removed) -> {args.cache_dir}')
    for request_name, files in by_request.items():
        print(f'  {request_name}')
        for entry in files:
            print(f"    {entry['created_at'][:10]}  {entry['task_name']} / {entry['name']}")


if __name__ == '__main__':
    main()
