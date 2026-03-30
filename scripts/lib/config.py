#!/usr/bin/env python3
import json
from pathlib import Path


DEFAULTS = {
    'strict_consistency': False,
    'window_days': 3,
    'min_body_chars': 300,
}


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_config() -> dict:
    root = workspace_root()
    # 优先读取 acecamp-raw/config.json（敏感配置）
    cfg_path = root / 'acecamp-raw' / 'config.json'
    # 如果不存在，回退到 skill 目录的模板
    if not cfg_path.exists():
        cfg_path = root / 'skills' / 'acecamp-minutes-ingest' / 'config.example.json'
    data = {}
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def resolve_bool(cli_value: bool, cfg: dict, key: str, default: bool = False) -> bool:
    if cli_value:
        return True
    return bool(cfg.get(key, default))


def resolve_int(cli_value: int, cfg: dict, key: str, default: int) -> int:
    if cli_value is not None:
        return int(cli_value)
    return int(cfg.get(key, default))
