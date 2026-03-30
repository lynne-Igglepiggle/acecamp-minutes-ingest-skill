from pathlib import Path
import shutil


def _ws_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if p.name == 'acecamp-raw':
            return p
    return start


def render_rendered_to_pdf(rendered_html: Path, rendered_pdf: Path) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError('playwright is required for PDF rendering') from e

    rendered_pdf.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(rendered_html.resolve().as_uri(), wait_until='networkidle')
            page.pdf(path=str(rendered_pdf), format='A4', print_background=True)
            browser.close()
    except Exception as e:
        raise RuntimeError(f'PDF render failed: {e}') from e
    return str(rendered_pdf)


def copy_pdf_to_share(rendered_pdf: Path, share_root: Path = None) -> Path:
    rendered_pdf = Path(rendered_pdf)
    if rendered_pdf is None or not rendered_pdf.exists():
        raise ValueError('rendered_pdf not found')

    if share_root is None:
        share_root = Path('share')
    else:
        share_root = Path(share_root)

    ws_root = _ws_root(rendered_pdf)
    if not share_root.is_absolute():
        share_root = ws_root / share_root

    share_root.mkdir(parents=True, exist_ok=True)
    dst = share_root / rendered_pdf.name
    shutil.copy2(rendered_pdf, dst)
    return dst
