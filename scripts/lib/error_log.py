#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


def append_error_log(ws_root: Path, article_id: str, stage: str, error_type: str, error_message: str, source_url: str = '', extra: Optional[Dict[str, Any]] = None):
    log_path = ws_root / 'acecamp-raw' / 'logs' / 'error-log.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        'time': datetime.now().isoformat(timespec='seconds'),
        'article_id': str(article_id or ''),
        'stage': stage,
        'error_type': error_type,
        'error_message': error_message,
        'source_url': source_url,
        'action_taken': 'stopped',
    }
    if extra:
        rec.update(extra)
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
