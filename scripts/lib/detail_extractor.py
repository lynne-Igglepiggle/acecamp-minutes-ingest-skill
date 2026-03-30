import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright


def _clean_text(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '')).strip()


def _clean_multiline_text(text: str) -> str:
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in (text or '').splitlines()]
    return '\n'.join([ln for ln in lines if ln])


def _dedup_keep_order(items):
    out = []
    seen = set()
    for x in items:
        x = _clean_text(x)
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _normalize_tags(items):
    tags = _dedup_keep_order(items)
    atomic = [t for t in tags if len(t) <= 8]
    out = []
    for t in tags:
        if len(t) > 8:
            matched = [a for a in atomic if a != t and a in t]
            if len(matched) >= 2:
                continue
        out.append(t)
    return _dedup_keep_order(out)


def _find_page(browser, url_prefix: str):
    for ctx in browser.contexts:
        for page in ctx.pages:
            if page.url.startswith(url_prefix):
                return page
    return None


def extract_detail_dict(url: str, cdp_url: str = 'http://127.0.0.1:18800') -> dict:
    js = r'''
() => {
  const txt = (el) => (el && el.textContent ? el.textContent.replace(/\s+/g, ' ').trim() : '');
  const title = txt(document.querySelector('main p'));

  const topBlock = Array.from(document.querySelectorAll('main div')).find(el => txt(el).includes('行业：'));
  const topText = txt(topBlock || document.querySelector('main'));

  const dateMatch = (topText.match(/\d{4}\/\d{2}\/\d{2}\s+\d{2}:\d{2}:\d{2}/) || [''])[0];
  const readMatch = topText.match(/阅读\s*(\d+)/);
  const likeMatch = topText.match(/点赞\s*(\d+)/);
  const wordMatch = (topText.match(/本文共\d+字，预计阅读时间\d+分钟/) || [''])[0];
  const industryMatch = topText.match(/行业：([^\n]+?)(?=\d{4}\/\d{2}\/\d{2}|阅读\s*\d+|点赞\s*\d+|AI\s*速览|要点|本文共|已享VIP免费|$)/);
  const industry = industryMatch ? industryMatch[1].trim() : '';

  const keyLabel = Array.from(document.querySelectorAll('main p, main div')).find(el => txt(el) === '要点');
  let key = '';
  if (keyLabel && keyLabel.parentElement) {
    const pointsNode = keyLabel.parentElement.querySelector('.points.pre') || keyLabel.parentElement.children[1];
    if (pointsNode) {
      key = (pointsNode.innerText || pointsNode.textContent || '').trim();
    }
  }

  const qlEditor = document.querySelector('#quill-preview-content .ql-editor') || document.querySelector('.ql-editor');
  const bodyContainer = Array.from(document.querySelectorAll('main div')).find(el => txt(el).includes('以下内容为专家分享，仅供参考，不构成任何投资建议。'));
  const bodyRoot = qlEditor || bodyContainer || null;

  let bodyHtml = '';
  let body = '';
  if (bodyRoot) {
    bodyHtml = bodyRoot.innerHTML || '';
    const temp = document.createElement('div');
    temp.innerHTML = bodyHtml;
    body = Array.from(temp.querySelectorAll('p, h1, h2, h3, li, blockquote')).map(el => txt(el)).filter(Boolean).join('\n');
  }

  const iq = Array.from(document.querySelectorAll('a[href*="/chat?title="]')).map(el => txt(el)).filter(Boolean).join('\n');

  const tags = (() => {
    const container = document.querySelector('main .article-type.tags-style.mt-8');
    if (!container) return [];
    const tagNodes = Array.from(container.querySelectorAll('.tag-width, .hashtag'));
    const vals = tagNodes.map(el => txt(el)).filter(Boolean);
    const cleaned = vals
      .map(t => t.replace(/^#/, '').trim())
      .filter(t => t && t.length <= 20 && !/[，,\/]/.test(t));
    return Array.from(new Set(cleaned));
  })();

  const authorLinks = Array.from(document.querySelectorAll('a[href*="/organizer/"]')).map(el => txt(el)).filter(Boolean);
  const author = authorLinks[0] || '';

  let expert = '';
  const expertNode = document.querySelector('main .multi-clamp.multi-clamp-texts.pre.mb-20.v2-status-text-333')
    || document.querySelector('main .multi-clamp-text');
  if (expertNode) {
    expert = txt(expertNode);
  }

  return {
    title,
    pub: dateMatch,
    read: readMatch ? readMatch[1] : '',
    like: likeMatch ? likeMatch[1] : '',
    words: wordMatch,
    industry,
    key,
    body,
    body_html: bodyHtml,
    iq,
    expert,
    author,
    co: '',
    tags
  };
}
'''

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        page = _find_page(browser, url)
        if page is None:
            raise RuntimeError(f'detail page not found for url prefix: {url}')
        page.wait_for_load_state('networkidle')
        data = page.evaluate(js)

    data['title'] = _clean_text(data.get('title', ''))
    data['pub'] = _clean_text(data.get('pub', ''))
    data['industry'] = _clean_text(data.get('industry', ''))
    data['key'] = _clean_multiline_text(str(data.get('key', '')))
    data['iq'] = '\n'.join(_dedup_keep_order(str(data.get('iq', '')).splitlines()))
    data['author'] = _clean_text(data.get('author', ''))
    data['expert'] = _clean_text(data.get('expert', ''))
    data['tags'] = _normalize_tags(data.get('tags', []))
    return data


def extract_detail_to_file(url: str, output: str, cdp_url: str = 'http://127.0.0.1:18800') -> str:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = extract_detail_dict(url=url, cdp_url=cdp_url)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(out)
