#!/usr/bin/env python3
import argparse
from pathlib import Path
from lib.error_log import append_error_log


def main():
    ap = argparse.ArgumentParser(description='Append one normalized record to acecamp error-log.jsonl')
    ap.add_argument('--article-id', required=True)
    ap.add_argument('--stage', default='human_review')
    ap.add_argument('--error-type', default='HumanRaisedIssue')
    ap.add_argument('--message', required=True)
    ap.add_argument('--source-url', default='')
    ap.add_argument('--action-taken', default='logged')
    args = ap.parse_args()

    ws_root = Path(__file__).resolve().parents[3]
    append_error_log(
        ws_root=ws_root,
        article_id=args.article_id,
        stage=args.stage,
        error_type=args.error_type,
        error_message=args.message,
        source_url=args.source_url,
        extra={'action_taken': args.action_taken},
    )
    print(f'LOGGED {args.article_id} {args.error_type}')


if __name__ == '__main__':
    main()
