from __future__ import annotations

import html
import re
from pathlib import Path

from lib.source_rules import validate_source_file

FORBIDDEN_INTROS = []


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    i = text.find(start_marker)
    if i < 0:
        return ''
    j = text.find(end_marker, i + len(start_marker))
    return text[i:j if j >= 0 else len(text)]


def _extract_body_lines(md_text: str) -> list[str]:
    body = _extract_section(md_text, '## 三、正文', '## 四、智能追问')
    if not body:
        return []
    lines = []
    for ln in body.splitlines():
        if ln.startswith('### ') or ln.startswith('**') or ln.startswith('- ') or ln.startswith('* ') or '![' in ln or ln.strip():
            lines.append(ln)
    return lines


def _strip_q_markup(text: str) -> str:
    return text.strip()


def _extract_question_texts_from_source(md_text: str) -> list[str]:
    q_lines = []
    in_body = False
    for ln in md_text.splitlines():
        if ln.startswith('## 四、智能追问'):
            break
        if ln.startswith('## 三、正文'):
            in_body = True
            continue
        if not in_body:
            continue
        if ln.startswith('### '):
            text = _strip_q_markup(ln[4:])
            if text.endswith('？') or text.endswith('?'):
                q_lines.append(text)
    return q_lines


def _extract_q_html_texts(rendered: str) -> list[str]:
    vals = re.findall(r'<p class="q">\s*<strong>(.*?)</strong>\s*</p>', rendered, flags=re.S)
    return [html.unescape(re.sub(r'<[^>]+>', '', v)).strip() for v in vals]


def _count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def _count_all_patterns(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.S))


def _count_image_lines(md_lines: list[str]) -> int:
    return _count_all_patterns('\n'.join(md_lines), r'^!\[[^\]]*\]\([^\)]+\)$')


def _count_list_items(md_lines: list[str]) -> int:
    return sum(1 for ln in md_lines if re.match(r'^\s*(?:[-*]|\d+\.)\s+', ln))


def _count_markups(md_text: str, tag: str) -> int:
    return len(re.findall(fr'<{tag}>.*?</{tag}>', md_text, flags=re.S))


def _check_render_contains(src_md: str, rendered: str) -> list[str]:
    errs: list[str] = []
    if any(x in src_md for x in FORBIDDEN_INTROS):
        errs.append('source contains forbidden injected intro text')
    if '## 三、正文' not in src_md:
        errs.append('missing section: ## 三、正文')

    md_lines = _extract_body_lines(src_md)
    src_q = _extract_question_texts_from_source(src_md)
    rendered_q = _extract_q_html_texts(rendered)
    if src_q:
        if len(rendered_q) < len(src_q):
            errs.append(f'q count too low in rendered: src={len(src_q)} rendered={len(rendered_q)}')
        else:
            for i, sq in enumerate(src_q):
                if i >= len(rendered_q):
                    break
                if sq != rendered_q[i]:
                    norm_sq = re.sub(r'\s+', '', sq)
                    norm_rq = re.sub(r'\s+', '', rendered_q[i])
                    if norm_sq != norm_rq:
                        errs.append(f"q text mismatch at index {i + 1}: src='{sq}' rendered='{rendered_q[i]}'")
                        break

    red_src = _count_markups(src_md, 'red')
    blue_src = _count_markups(src_md, 'blue')
    rendered_red = _count_pattern(rendered, r'class="red"')
    rendered_blue = _count_pattern(rendered, r'class="blue"')
    if red_src > rendered_red:
        errs.append(f'red markup dropped: src={red_src} rendered={rendered_red}')
    if blue_src > rendered_blue:
        errs.append(f'blue markup dropped: src={blue_src} rendered={rendered_blue}')

    bold_src = _count_all_patterns('\n'.join(md_lines), r'\*\*[^\*]+\*\*')
    bold_rendered = _count_pattern(rendered, r'<strong>')
    if bold_src > 0 and bold_rendered == 0:
        errs.append('bold markdown present in source but no <strong> in rendered')

    li_src = _count_list_items(md_lines)
    li_rendered = _count_pattern(rendered, r'<li')
    if li_src > 0 and li_rendered < li_src:
        errs.append(f'list items dropped: src={li_src} rendered={li_rendered}')

    img_src = _count_image_lines(md_lines)
    img_rendered = _count_pattern(rendered, r'<img ')
    if img_src > 0 and img_rendered < img_src:
        errs.append(f'image tags dropped: src={img_src} rendered={img_rendered}')

    for intro in FORBIDDEN_INTROS:
        if intro in rendered:
            errs.append(f'forbidden intro rendered: {intro}')
    return errs


def run_check(source_path: Path, rendered_path: Path, allow_empty_body: bool = False, min_body_chars: int = 300) -> list[str]:
    errs: list[str] = []
    if not source_path.exists():
        return [f'source not found: {source_path}']
    if not rendered_path.exists():
        return [f'rendered not found: {rendered_path}']

    md = source_path.read_text(encoding='utf-8')
    rendered = rendered_path.read_text(encoding='utf-8')
    try:
        validate_source_file(source_path, allow_empty_body=allow_empty_body, min_body_chars=min_body_chars)
    except Exception as e:
        errs.append(f'validate_source_file failed: {e}')
    errs.extend(_check_render_contains(md, rendered))
    return errs
