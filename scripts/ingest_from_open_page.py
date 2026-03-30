#!/usr/bin/env python3
"""
AceCamp single-article main entrypoint.

ROLE IN THE SKILL:
- This is the PRIMARY entrypoint for ingesting one already-open AceCamp detail page.
- Use this for the normal "录入这一篇" workflow.
- It orchestrates: detail extraction -> source build -> ingest/render/index -> validation.

DESIGN NOTE:
- Keep this file as the user-facing single-article entry.
- `ingest_one.py` remains the downstream/source-level processor.
- Over time, more subprocess layers should be pulled inward here or into shared library code.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from lib.source_builder import build_source
from lib.detail_extractor import extract_detail_to_file

WS_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = WS_ROOT / 'skills' / 'acecamp-minutes-ingest' / 'scripts'


def run(cmd):
    """在工作区根目录执行一个子命令；若失败则输出已捕获的 stdout/stderr。"""
    proc = subprocess.run(cmd, cwd=WS_ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end='')
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end='')
        raise RuntimeError(f'command failed ({proc.returncode}): ' + ' '.join(cmd))


def slugify_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    text = text.replace('（', '').replace('）', '').replace('(', '').replace(')', '')
    text = text.replace('，', '').replace(',', '').replace('。', '').replace('.', '')
    text = text.replace('、', '').replace('—', '').replace('-', '')
    text = re.sub(r'\s+', '', text)
    return text[:max_len] or 'untitled'


def detect_detail_meta(detail_json: Path):
    """读取规范化后的 detail.json，并提取下游入库所需的 metadata。"""
    d = json.loads(detail_json.read_text(encoding='utf-8'))
    title = d.get('title', '').strip()
    pub = d.get('pub', '').strip()
    industry = d.get('industry', '').strip()
    tags = d.get('tags', []) if isinstance(d.get('tags', []), list) else []
    author = d.get('author', '').strip()
    co = d.get('co', '').strip()
    content_type = d.get('content_type', '').strip() or '纪要'

    article_date = ''
    if pub:
        m = re.match(r'(\d{4}/\d{2}/\d{2})', pub)
        if m:
            article_date = m.group(1).replace('/', '-')

    return {
        'title': title,
        'pub': pub,
        'article_date': article_date,
        'industry': industry,
        'tags': tags,
        'author': author,
        'co_publisher': co,
        'content_type': content_type,
    }


def main():
    """
    单篇 AceCamp 文章入库总控流程。

    执行阶段：
    1. 从已打开的详情页抽取 `detail.json`
    2. 根据抽取结果推导文件名和下游所需 metadata
    3. 通过 `lib.source_builder` 生成规范 `source.md`
    4. 委派给 `ingest_one.py` 完成 source 级处理
    5. 在最外层再做一次 output validation，确认最终产物合格后再返回成功

    这个文件应持续保持为“单篇主入口编排层”。
    更底层的转换、渲染、校验逻辑应放在 `lib/` 或下游处理器里，
    不要再反向堆回这个入口文件。
    """
    ap = argparse.ArgumentParser(description='One-shot AceCamp single-article ingestion from an already-open detail page')
    ap.add_argument('--url', required=True, help='detail page URL')
    # 目前仍要求显式传入 article-id；后续如有需要，可再改成从 URL 自动推导。
    ap.add_argument('--article-id', required=True)
    ap.add_argument('--crawl-date', default=datetime.now().strftime('%Y-%m-%d'))
    ap.add_argument('--record-time', default=datetime.now().strftime('%Y-%m-%d %H:%M:%S +08:00'))
    ap.add_argument('--provider', default='acecamptech')
    ap.add_argument('--min-body-chars', type=int, default=300)
    ap.add_argument('--ensure-login', action='store_true', help='在入库前先调用 login_policy.py 执行标准登录（当前仅输出执行脚本，由上层浏览器链消费）')
    args = ap.parse_args()

    # 第 1 阶段：从当前已打开的浏览器详情页抽取结构化 detail 字段。
    # 这里保留为独立的页面抽取边界，因为浏览器/CDP 访问、页面可见态判断
    # 和后续 markdown/source 生成本来就是两类不同职责。
    detail_json = WS_ROOT / 'acecamp-raw' / 'tmp' / f'{args.article_id}.detail.json'
    out_detail = extract_detail_to_file(url=args.url, output=str(detail_json))
    print(out_detail)

    # 第 2 阶段：整理规范化 metadata，用于文件命名和下游入库。
    # 这里的优先级是：先信任页面抽取结果，其次才用 CLI 参数兜底。
    meta = detect_detail_meta(detail_json)
    article_date = meta['article_date'] or args.crawl_date
    title_slug = slugify_filename(meta['title'])
    base = f"{article_date}_{args.provider}_{args.article_id}_{title_slug}_{args.crawl_date}"

    # 第 3 阶段：分配最终产物路径。
    # 目录语义：
    # - source/   只放规范 source markdown
    # - rendered/ 只放 HTML
    source_path = WS_ROOT / 'acecamp-raw' / 'source' / f'{base}.md'
    rendered_path = WS_ROOT / 'acecamp-raw' / 'rendered' / f'{base}.html'

    # 第 4 阶段：根据结构化 detail.json 生成规范 source markdown。
    # 问句标题、格式保真、标签、专家字段等，都是在这一步收敛进标准 source 结构。
    out = build_source(str(detail_json), str(source_path), args.record_time, args.url, str(args.article_id))
    print(out)

    # 第 5 阶段：交给 source 级下游处理器继续执行。
    # ingest_one.py 负责 html 渲染、pdf 生成、manifest/index 同步、一致性修正等工作。
    ingest_cmd = [
        'python3', str(SCRIPTS / 'ingest_one.py'),
        '--source-path', str(source_path),
        '--rendered-path', str(rendered_path),
        '--source-url', args.url,
        '--record-time', args.record_time,
        '--article-id', str(args.article_id),
        '--article-date', article_date,
        '--provider', args.provider,
        '--article-title', meta['title'],
        '--crawl-date', args.crawl_date,
        '--content-type', meta['content_type'],
        '--industry', meta['industry'],
        '--tags', ','.join(meta['tags']),
        '--author', meta['author'],
        '--co-publisher', meta['co_publisher'],
        '--min-body-chars', str(args.min_body_chars),
    ]
    run(ingest_cmd)

    # 第 6 阶段：在入口层再显式跑一次最终校验。
    # 虽然 ingest_one.py 内部已经会做校验，但这里仍保留最外层 guard，
    # 确保单篇主入口只有在最终产物通过验收后才返回成功。
    from lib.output_validator import run_check
    errs = run_check(source_path=source_path, rendered_path=rendered_path, allow_empty_body=False, min_body_chars=args.min_body_chars)
    if errs:
        for e in errs:
            print(' -', e)
        raise RuntimeError('ACECAMP_VALIDATION_FAIL')
    print('ACECAMP_VALIDATION_OK')

    # 第 7 阶段：输出机器可读的成功结果，供外层调用方或包装器继续使用。
    print(json.dumps({
        'ok': True,
        'article_id': str(args.article_id),
        'source_path': str(source_path),
        'rendered_path': str(rendered_path),
        'detail_json': str(detail_json),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
