import json
import re
from datetime import datetime
from pathlib import Path


_DETAIL_RE = re.compile(r'/article/detail/(\d+)')
_DATE_RE = re.compile(r'(\d{4}/\d{2}/\d{2})')
_RELATIVE_TIME_RE = re.compile(r'\d+小时前|\d+分钟前|刚刚')


def _load_manifest_ids(path: Path):
    ids = set()
    if not path.exists():
        return ids
    for ln in path.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        try:
            ids.add(str(json.loads(ln).get('article_id', '')))
        except Exception:
            pass
    return ids


def _extract_date(text: str):
    if _RELATIVE_TIME_RE.search(text):
        return None
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), '%Y/%m/%d')
    except Exception:
        return None


def _entry_sort_key(entry: dict):
    dt = entry.get('date')
    has_relative = bool(entry.get('has_relative_time'))
    if has_relative:
        return (2, datetime.max, entry.get('line_no', 0))
    if dt is not None:
        return (1, dt, entry.get('line_no', 0))
    return (0, datetime.min, entry.get('line_no', 0))


def _parse_article_entries(snapshot_text: str):
    entries = []
    seen = set()
    lines = snapshot_text.splitlines()
    for i, ln in enumerate(lines):
        m = _DETAIL_RE.search(ln)
        if not m:
            continue
        aid = m.group(1)
        if aid in seen:
            continue
        seen.add(aid)
        prev_ln = lines[i - 1] if i > 0 else ''
        text = (prev_ln + ' ' + ln).strip()
        entries.append({
            'id': aid,
            'text': text,
            'line_no': i,
            'date': _extract_date(text),
            'has_relative_time': bool(_RELATIVE_TIME_RE.search(text)),
        })
    entries.sort(key=_entry_sort_key, reverse=True)
    return entries


def pick_candidates(snapshot_path: str, manifest_path: str = 'acecamp-raw/index/manifest.jsonl', allow_backfill: bool = False, window_days: int = 3, today: str = '', max_recent: int = 30) -> dict:
    txt = Path(snapshot_path).read_text(encoding='utf-8')
    all_entries = _parse_article_entries(txt)
    entries = all_entries[:max_recent]

    candidate_ids = [e['id'] for e in entries]
    manifest_ids = _load_manifest_ids(Path(manifest_path))
    picked = [x for x in candidate_ids if x not in manifest_ids]

    return {
        'ok': True,
        'allowBackfill': allow_backfill,
        'windowDays': None,
        'maxRecent': max_recent,
        'totalSeen': len(all_entries),
        'picked': picked,
        'usedWindowFilter': False,
    }
