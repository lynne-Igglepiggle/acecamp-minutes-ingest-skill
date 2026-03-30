#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


CASES = {
    '70560067': {
        'required': False,
        'checks': {
            'min_body_chars': 800,
            'min_q': 5,
        },
        'desc': '中文锚点正文提取（历史回归样本）',
    },
    '70560083': {
        'required': False,
        'checks': {
            'min_body_chars': 800,
            'min_q': 5,
        },
        'desc': '英文锚点正文提取（历史回归样本）',
    },
    '70560077': {
        'required': False,
        'checks': {
            'min_body_chars': 1000,
            'min_q': 10,
        },
        'desc': '中文问号问题蓝色样式（历史回归样本）',
    },
    '70560221': {
        'required': True,
        'checks': {
            'min_body_chars': 4000,
            'min_q': 10,
            'min_tags': 3,
            'must_contain': ['发布人：共享调研纪要'],
        },
        'desc': '多标签 / 共享调研纪要 / 长正文 / 问题标题样式',
    },
    '70560289': {
        'required': True,
        'checks': {
            'min_body_chars': 1300,
            'min_q': 5,
            'key_min_lines': 2,
        },
        'desc': '要点原始换行 / 问题标题样式',
    },
    '70560194': {
        'required': True,
        'checks': {
            'min_body_chars': 1200,
            'min_images': 1,
            'min_ordered_list_items': 1,
            'min_unordered_list_items': 1,
        },
        'desc': '图片 / 有序列表 / 无序列表',
    },
}


def find_single(glob_pat: str):
    matches = sorted(Path().glob(glob_pat))
    return matches[0] if matches else None


def body_section(source_text: str) -> str:
    m = re.search(r'## 三、正文[\s\S]*?(?=\n## 四、智能追问|\Z)', source_text)
    return m.group(0) if m else ''


def body_len_from_source(source_text: str) -> int:
    return len(re.sub(r'\s+', '', body_section(source_text)))


def key_section(source_text: str) -> str:
    m = re.search(r'## 二、要点（页面原文）[\s\S]*?(?=\n## 三、正文|\Z)', source_text)
    return m.group(0) if m else ''


def key_line_count(source_text: str) -> int:
    sec = key_section(source_text)
    lines = [ln.strip() for ln in sec.splitlines() if ln.strip() and not ln.startswith('## ')]
    return len(lines)


def tag_count(source_text: str) -> int:
    m = re.search(r'## 五、标签（页面可见）[\s\S]*?(?=\n## 六、专家与作者信息|\Z)', source_text)
    if not m:
        return 0
    sec = m.group(0)
    return sum(1 for ln in sec.splitlines() if ln.startswith('- '))


def rendered_q_count(rendered_html: str) -> int:
    return rendered_html.count('class="q"')


def image_count(source_text: str, rendered_html: str) -> tuple[int, int]:
    src = len(re.findall(r'^!\[[^\]]*\]\([^\)]+\)$', source_text, flags=re.M))
    rnd = rendered_html.count('<img ')
    return src, rnd


def list_counts(source_text: str) -> tuple[int, int]:
    body = body_section(source_text)
    ol = len(re.findall(r'^\s*\d+\.\s+', body, flags=re.M))
    ul = len(re.findall(r'^\s*-\s+', body, flags=re.M))
    return ol, ul


def run_case(case_id: str):
    cfg = CASES[case_id]
    src = find_single(f'acecamp-raw/source/*_{case_id}_*.md')
    rnd = find_single(f'acecamp-raw/rendered/*_{case_id}_*.html')

    if not src or not rnd:
        if cfg.get('required', False):
            return False, f'{case_id} missing required file(s): source={bool(src)} rendered={bool(rnd)}'
        return True, f'{case_id} SKIP optional missing file(s): source={bool(src)} rendered={bool(rnd)}'

    s = src.read_text(encoding='utf-8')
    h = rnd.read_text(encoding='utf-8')
    checks = cfg['checks']

    if 'min_body_chars' in checks:
        blen = body_len_from_source(s)
        if blen < checks['min_body_chars']:
            return False, f'{case_id} body too short: {blen} < {checks["min_body_chars"]}'

    if 'min_q' in checks:
        q_count = rendered_q_count(h)
        if q_count < checks['min_q']:
            return False, f'{case_id} q_count too low: {q_count} < {checks["min_q"]}'

    if 'min_tags' in checks:
        t_count = tag_count(s)
        if t_count < checks['min_tags']:
            return False, f'{case_id} tag_count too low: {t_count} < {checks["min_tags"]}'

    if 'key_min_lines' in checks:
        k_count = key_line_count(s)
        if k_count < checks['key_min_lines']:
            return False, f'{case_id} keypoint line count too low: {k_count} < {checks["key_min_lines"]}'

    if 'min_images' in checks:
        src_img, rnd_img = image_count(s, h)
        if src_img < checks['min_images']:
            return False, f'{case_id} source image count too low: {src_img} < {checks["min_images"]}'
        if rnd_img < checks['min_images']:
            return False, f'{case_id} rendered image count too low: {rnd_img} < {checks["min_images"]}'

    if 'min_ordered_list_items' in checks or 'min_unordered_list_items' in checks:
        ol, ul = list_counts(s)
        if 'min_ordered_list_items' in checks and ol < checks['min_ordered_list_items']:
            return False, f'{case_id} ordered list count too low: {ol} < {checks["min_ordered_list_items"]}'
        if 'min_unordered_list_items' in checks and ul < checks['min_unordered_list_items']:
            return False, f'{case_id} unordered list count too low: {ul} < {checks["min_unordered_list_items"]}'

    if 'must_contain' in checks:
        for text in checks['must_contain']:
            if text not in s:
                return False, f'{case_id} missing required text: {text}'

    summary = []
    summary.append(f'body={body_len_from_source(s)}')
    summary.append(f'q={rendered_q_count(h)}')
    if 'min_tags' in checks:
        summary.append(f'tags={tag_count(s)}')
    if 'key_min_lines' in checks:
        summary.append(f'key_lines={key_line_count(s)}')
    if 'min_images' in checks:
        src_img, rnd_img = image_count(s, h)
        summary.append(f'img={src_img}/{rnd_img}')
    if 'min_ordered_list_items' in checks or 'min_unordered_list_items' in checks:
        ol, ul = list_counts(s)
        summary.append(f'ol={ol}')
        summary.append(f'ul={ul}')

    return True, f"{case_id} PASS {' '.join(summary)} ({cfg['desc']})"


def main():
    ap = argparse.ArgumentParser(description='Run AceCamp regression checks for representative edge samples')
    ap.add_argument('--cases', default='70560067,70560083,70560077,70560221,70560289,70560194', help='comma-separated case ids')
    args = ap.parse_args()

    all_ok = True
    for case_id in [x.strip() for x in args.cases.split(',') if x.strip()]:
        if case_id not in CASES:
            print(f'{case_id} SKIP unknown case')
            continue
        ok, msg = run_case(case_id)
        print(msg)
        all_ok = all_ok and ok

    if not all_ok:
        raise SystemExit(1)
    print('REGRESSION_OK')


if __name__ == '__main__':
    main()
