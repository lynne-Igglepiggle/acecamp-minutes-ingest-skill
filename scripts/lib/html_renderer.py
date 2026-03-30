from pathlib import Path
import re, html

TEMPLATE_CSS = """
body { font-family: -apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,\"PingFang SC\",\"Noto Sans CJK SC\",\"Microsoft YaHei\",sans-serif; margin: 24px auto; max-width: 980px; line-height: 1.72; color: #111; padding: 0 16px; }
h1,h2,h3 { line-height: 1.35; }
.meta { background: #f6f8fa; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 14px; margin: 12px 0 20px; }
.muted { color: #555; }
.section { margin-top: 24px; }
.tag { display:inline-block; padding:2px 8px; margin-right:8px; background:#eef2ff; border-radius:999px; font-size:12px; }
p { margin: 10px 0; white-space: pre-wrap; }
.q { color:#1d4ed8; }
.blue { color:#3b82f6; }
.red { color:#dc2626; }
.sp { height: 6px; }
.body-list { margin: 8px 0 8px 20px; }
.body-list li { margin: 6px 0; }
.body-img { max-width: 100%; border-radius: 8px; display:block; margin: 10px 0; }
.keypoint-box { background:rgb(254, 248, 234); border:1px solid #f2d675; border-radius:10px; padding:12px 14px; }
.keypoint-box ul{ margin:0; padding-left:20px; }
.keypoint-box li{ margin:6px 0; }
.tldr-box { background: linear-gradient(180deg, #eef6ff 0%, #e3efff 100%); border: 1px solid #bfdbfe; border-left: 4px solid #60a5fa; border-radius: 12px; padding: 14px 16px; margin: 10px 0 16px; color: #1e3a8a; }
.tldr-box p { margin: 0; white-space: normal; }
.tldr-box strong { color: #1d4ed8; }
"""


def _render_inline(text: str) -> str:
    text = re.sub(r'<blue>([\s\S]*?)</blue>', r'{{BLUE_START}}\1{{BLUE_END}}', text)
    text = re.sub(r'<red>([\s\S]*?)</red>', r'{{RED_START}}\1{{RED_END}}', text)
    s = html.escape(text)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = s.replace('{{BLUE_START}}', '<span class="blue">').replace('{{BLUE_END}}', '</span>')
    s = s.replace('{{RED_START}}', '<span class="red">').replace('{{RED_END}}', '</span>')
    return s


def parse_md(md_text: str):
    lines = md_text.splitlines()
    meta, body, questions, tags, expert = {}, [], [], [], []
    keypoints = ""
    sec = ""

    for ln in lines:
        if ln.startswith("## "):
            sec = ln[3:].strip()
            continue

        if sec == "一、基础信息" and ln.startswith("- "):
            if "：" in ln[2:]:
                k, v = ln[2:].split("：", 1)
                meta[k.strip()] = v.strip()
        elif sec.startswith("二、要点"):
            if ln.strip() and not ln.startswith("##"):
                keypoints += (ln + "\n")
        elif sec.startswith("三、正文"):
            if ln.startswith("> "):
                body.append(("quote", ln[2:].strip()))
            elif ln.startswith("### "):
                text = ln[4:].strip()
                if text.endswith('？') or text.endswith('?'):
                    body.append(("q", text))
                else:
                    body.append(("h3", text))
            elif ln.startswith("#### "):
                body.append(("h4", ln[5:].strip()))
            elif ln.startswith("##### "):
                body.append(("h5", ln[6:].strip()))
            elif re.match(r'^!\[[^\]]*\]\([^\)]+\)$', ln.strip()):
                m_img = re.match(r'^!\[([^\]]*)\]\(([^\)]+)\)$', ln.strip())
                alt = (m_img.group(1) or '').strip()
                src = (m_img.group(2) or '').strip()
                body.append(("img", (alt, src)))
            elif re.match(r'^\s*[-*]\s+.+', ln):
                indent = len(ln) - len(ln.lstrip(' '))
                level = max(0, indent // 2)
                item = re.sub(r'^\s*[-*]\s+', '', ln).strip()
                body.append(("ul_li", (level, item)))
            elif re.match(r'^\s*\d+\.\s+.+', ln):
                indent = len(ln) - len(ln.lstrip(' '))
                level = max(0, indent // 2)
                num = int(re.match(r'^\s*(\d+)\.', ln).group(1))
                item = re.sub(r'^\s*\d+\.\s+', '', ln).strip()
                body.append(("ol_li", (level, num, item)))
            elif ln.strip():
                body.append(("p", ln.strip()))
            else:
                body.append(("sp", ""))
        elif sec.startswith("四、智能追问"):
            m = re.match(r"\d+\.\s*(.+)", ln.strip())
            if m:
                questions.append(m.group(1))
        elif sec.startswith("五、标签") and ln.startswith("- "):
            tags.append(ln[2:].strip())
        elif sec.startswith("六、专家与作者信息") and ln.startswith("- "):
            expert.append(ln[2:].strip())

    raw_title = meta.get("标题", "")
    clean_title = re.sub(r"（[^）]*）|\([^)]*\)", "", raw_title).strip()

    return {
        "meta": meta,
        "clean_title": clean_title,
        "keypoints": keypoints.strip(),
        "body": body,
        "questions": questions,
        "tags": tags,
        "expert": expert,
    }


def keypoint_items(text: str):
    t = text.replace("本文核心要点包括：", "").strip()
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    parts = []
    for ln in lines:
        m = re.match(r"^\d+[、，\.]\s*(.+)$", ln)
        if m:
            parts.append(m.group(1).strip(" ，。"))
        else:
            parts.append(ln.strip(" ，。"))
    out = []
    seen = set()
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out if out else [text]


def render(parsed: dict, source_url: str, record_time: str, article_id: str):
    meta = parsed["meta"]
    title = parsed["clean_title"]
    body_html = []
    list_open = None
    for t, c in parsed["body"]:
        if t in ("q", "p", "sp", "img", "h3", "h4", "h5", "quote") and list_open:
            body_html.append(f'</{list_open}>')
            list_open = None
        if t == "q":
            body_html.append(f'<p class="q"><strong>{_render_inline(c)}</strong></p>')
        elif t == "quote":
            body_html.append(f'<blockquote class="tldr-box"><p>{_render_inline(c)}</p></blockquote>')
        elif t == "h3":
            body_html.append(f'<h3>{_render_inline(c)}</h3>')
        elif t == "h4":
            cleaned = re.sub(r'^\*\*(.*?)\*\*$', r'\1', c)
            body_html.append(f'<h4>{_render_inline(cleaned)}</h4>')
        elif t == "h5":
            cleaned = re.sub(r'^\*\*(.*?)\*\*$', r'\1', c)
            body_html.append(f'<h5>{_render_inline(cleaned)}</h5>')
        elif t == "p":
            body_html.append(f"<p>{_render_inline(c)}</p>")
        elif t == "ul_li":
            level, item = c
            if list_open != "ul":
                if list_open:
                    body_html.append(f'</{list_open}>')
                body_html.append('<ul class="body-list">')
                list_open = "ul"
            body_html.append(f"<li style='margin-left:{level*16}px'>{_render_inline(item)}</li>")
        elif t == "ol_li":
            level, num, item = c
            if list_open != "ol":
                if list_open:
                    body_html.append(f'</{list_open}>')
                body_html.append('<ol class="body-list">')
                list_open = "ol"
            body_html.append(f"<li style='margin-left:{level*16}px' value='{num}'>{_render_inline(item)}</li>")
        elif t == "img":
            alt, src = c
            body_html.append(f"<img class='body-img' src='{html.escape(src)}' alt='{html.escape(alt)}' loading='lazy' referrerpolicy='no-referrer' />")
        else:
            body_html.append('<div class="sp"></div>')
    if list_open:
        body_html.append(f'</{list_open}>')

    q_html = "".join(f"<p>{i+1}. {html.escape(q)}</p>" for i, q in enumerate(parsed["questions"]))
    tag_html = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in parsed["tags"])
    expert_html = "\n".join(f"<p>{html.escape(x)}</p>" for x in parsed["expert"])
    kp_items = keypoint_items(parsed["keypoints"])
    kp_html = "".join(f"<li>{html.escape(i)}</li>" for i in kp_items)

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>{TEMPLATE_CSS}</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="meta">
    <div><strong>article_id：</strong>{html.escape(article_id)}</div>
    <div><strong>来源：</strong><a href="{html.escape(source_url)}" target="_blank">{html.escape(source_url)}</a></div>
    <div><strong>记录时间：</strong>{html.escape(record_time)}</div>
  </div>

  <div class="section">
    <h2>一、基本信息</h2>
    <p><strong>标题：</strong>{html.escape(title)}</p>
    <p class="muted">内容类型：{html.escape(meta.get('内容类型',''))}｜权限：{html.escape(meta.get('权限',''))}｜标识：{html.escape(meta.get('标识',''))}｜行业：{html.escape(meta.get('行业',''))}</p>
    <p class="muted">发布时间：{html.escape(meta.get('发布时间',''))}｜阅读：{html.escape(meta.get('阅读',''))}｜点赞：{html.escape(meta.get('点赞',''))}｜字数/阅读时长：{html.escape(meta.get('字数/阅读时长',''))}｜VIP状态：{html.escape(meta.get('VIP状态',''))}</p>
  </div>

  <div class="section">
    <h2>二、要点</h2>
    <div class="keypoint-box"><ul>{kp_html}</ul></div>
  </div>

  <div class="section">
    <h2>三、正文</h2>
    {''.join(body_html)}
  </div>

  <div class="section">
    <h2>四、智能追问</h2>
    {q_html}
  </div>

  <div class="section">
    <h2>五、标签</h2>
    {tag_html}
  </div>

  <div class="section">
    <h2>六、专家与作者信息</h2>
    {expert_html}
  </div>
</body>
</html>
'''


def render_file(input_md: str, output_html: str, source_url: str, record_time: str, article_id: str) -> str:
    md_text = Path(input_md).read_text(encoding="utf-8")
    parsed = parse_md(md_text)
    html_doc = render(parsed, source_url, record_time, article_id)
    out = Path(output_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return str(out)
