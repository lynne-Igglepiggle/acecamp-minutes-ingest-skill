#!/usr/bin/env python3
"""
AceCamp keyword-search main entrypoint.

ROLE IN THE SKILL:
- This is the PRIMARY entrypoint for keyword/search-based ingestion.
- Use it for workflows like: "录入一篇 AXTI 相关纪要" or "按关键词批量入库".
- It orchestrates the search-driven path, then delegates chosen detail pages into
  `ingest_from_open_page.py`.

CURRENT IMPLEMENTATION SCOPE:
- Supports the local/non-browser part completely:
  - parse search result snapshot text
  - pick un-ingested candidates from manifest
  - derive detail URLs
  - emit executable delegation commands into `ingest_from_open_page.py`
  - optionally execute those commands
- Browser search/open steps are still external for now, but the contract is now fixed.

DESIGN NOTE:
- Keep this file as the ONLY keyword/search top-level entrypoint.
- Do not scatter ad-hoc keyword ingestion logic across chat turns or other scripts.
"""

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from lib.candidate_picker import pick_candidates

WS_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = WS_ROOT / 'skills' / 'acecamp-minutes-ingest' / 'scripts'


def run_json(cmd):
    proc = subprocess.run(cmd, cwd=WS_ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, end='')
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end='')
        raise RuntimeError(f'command failed ({proc.returncode}): ' + ' '.join(cmd))
    return json.loads(proc.stdout)


def run_passthrough(cmd):
    proc = subprocess.run(cmd, cwd=WS_ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end='')
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end='')
        raise RuntimeError(f'command failed ({proc.returncode}): ' + ' '.join(cmd))


def build_ingest_cmd(article_id: str, url: str, crawl_date: str, record_time: str):
    return [
        'python3', str(SCRIPTS / 'ingest_from_open_page.py'),
        '--url', url,
        '--article-id', article_id,
        '--crawl-date', crawl_date,
        '--record-time', record_time,
    ]


def shell_join(cmd):
    return ' '.join(shlex.quote(x) for x in cmd)


def build_delegations(selected_ids, crawl_date: str, record_time: str):
    items = []
    for aid in selected_ids:
        url = f'https://www.acecamptech.com/article/detail/{aid}'
        cmd = build_ingest_cmd(aid, url, crawl_date, record_time)
        items.append({
            'article_id': aid,
            'url': url,
            'delegate_to': 'ingest_from_open_page.py',
            'command': cmd,
            'command_shell': shell_join(cmd),
        })
    return items


def main():
    ap = argparse.ArgumentParser(description='AceCamp keyword/search ingestion entrypoint')
    ap.add_argument('--keyword', required=True, help='Search keyword, e.g. AXTI / 磷化铟 / HBM')
    ap.add_argument('--snapshot-path', required=True, help='Saved search result snapshot text; must include /article/detail/<id> links for candidate extraction')
    ap.add_argument('--manifest-path', default='acecamp-raw/index/manifest.jsonl')
    ap.add_argument('--mode', default='newest_one', choices=['newest_one', 'all_new'])
    ap.add_argument('--execute', action='store_true', help='Immediately execute delegation command(s) after selection')
    args = ap.parse_args()

    now = datetime.now()
    crawl_date = now.strftime('%Y-%m-%d')
    record_time = now.strftime('%Y-%m-%d %H:%M:%S +08:00')

    picked = pick_candidates(
        snapshot_path=args.snapshot_path,
        manifest_path=args.manifest_path,
        allow_backfill=False,
        window_days=0,
        today='',
        max_recent=30,
    )

    ids = picked.get('picked', [])
    selected = ids[:1] if args.mode == 'newest_one' else ids
    delegations = build_delegations(selected, crawl_date, record_time)

    if args.execute:
        for item in delegations:
            run_passthrough(item['command'])

    print(json.dumps({
        'ok': True,
        'entrypoint': 'search_and_ingest.py',
        'keyword': args.keyword,
        'windowDays': None,
        'allowBackfill': False,
        'mode': args.mode,
        'picked': picked.get('picked', []),
        'selected': selected,
        'detail_urls': [x['url'] for x in delegations],
        'delegation': delegations,
        'executed': bool(args.execute),
        'message': 'Open selected detail URL(s) and run the emitted command(s), or pass --execute to run them immediately.'
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
