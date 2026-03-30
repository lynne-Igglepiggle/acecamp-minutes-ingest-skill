import json


def resolve_tab_from_tabs_json(tabs_json: str, match_url: str) -> dict:
    data = json.loads(tabs_json)
    tabs = data.get('tabs', []) if isinstance(data, dict) else []
    for t in tabs:
        url = str(t.get('url', ''))
        if match_url in url:
            return {
                'ok': True,
                'found': True,
                'targetId': t.get('targetId'),
                'url': url,
                'title': t.get('title', ''),
                'mustReuse': True,
                'allowOpen': False,
                'policy': 'reuse-existing-tab-first',
            }
    return {
        'ok': True,
        'found': False,
        'mustReuse': False,
        'allowOpen': True,
        'policy': 'reuse-existing-tab-first',
    }


def guard_open_from_decision(resolve_json: str, planned_action: str) -> tuple[dict, int]:
    decision = json.loads(resolve_json)
    if planned_action == 'open' and decision.get('found'):
        return ({
            'ok': False,
            'error': 'OPEN_BLOCKED_REUSE_REQUIRED',
            'message': 'Matching tab exists; must reuse targetId instead of opening new tab.',
            'targetId': decision.get('targetId'),
        }, 2)

    return ({
        'ok': True,
        'plannedAction': planned_action,
        'found': bool(decision.get('found')),
        'allowed': True,
    }, 0)
