---
name: acecamp-minutes-ingest
description: Ingest AceCamp articles (especially 科技向纪要) into local knowledge files with a strict, human-reviewed workflow. Use when user asks to collect/录入 AceCamp 内容, create source+rendered files, sync manifest/index, enforce filename convention, or check missing daily minutes.
---

# acecamp-minutes-ingest

Execute AceCamp ingestion in this fixed order.

## 1) Main Entrypoints

This skill has two top-level entrypoints:

1. `scripts/ingest_from_open_page.py`
   - **Primary single-article entrypoint**
   - Use when one AceCamp detail page is already open and you want to ingest that page.

2. `scripts/search_and_ingest.py`
   - **Primary keyword/search entrypoint**
   - Use when the task starts from a keyword, company, ticker, or search intent.
   - Input contract: the saved search snapshot must include `/article/detail/<id>` links; plain visible text without detail links is not sufficient.

`ingest_one.py` is a downstream/source-level processor, not a peer top-level entrypoint.
Think of it as: `source.md -> rendered/html/pdf/index/validate`.

## 2) Prerequisites

Before running:
- `python3` available
- `openpyxl` installed
- `playwright` installed
- `acecamp-raw/config.json` exists and is valid

Sensitive config must live in:
- `acecamp-raw/config.json`

Preflight command:
```bash
python3 skills/acecamp-minutes-ingest/scripts/preflight_check.py
```

If preflight fails, stop and fix it before ingestion.

## 3) Hard Rules

### 3.1 Login / page-state rules
- AceCamp login page must be treated as a **no-slider login flow by default**.
- Standard flow is: switch to password login -> fill account/password -> check agreement -> click login.
- For phone/password login, focus the password field and use a **real browser-level Enter keypress** as the primary submit action.
- Synthetic DOM keyboard-event dispatch is not reliable enough for AceCamp submit; prefer browser/tool-level keypress after the password field is visibly focused.
- Login-button click is secondary only; do not treat it as the default submit path.
- Do **not** conclude slider/captcha exists from snapshot/DOM text.
- Text like “安全验证 / 拖动下方拼图完成验证 / 验证错误” is **not sufficient evidence** by itself.
- Only if a real **foreground, visible, blocking** slider/captcha layer is present after submit should it be treated as an exception.
- Do not stop for manual intervention unless that exception is visibly shown on the real rendered page.
- Use `scripts/login_policy.py` as the canonical login policy reference.
- Runtime execution requirement: after filling the password field, the agent should use the browser tool to **focus the password field and call a real `press Enter` action**, instead of treating JS evaluate/dispatch as the final submit step.

### 3.2 Content fidelity rules
- Source正文必须保留页面可见原文，不得摘要改写。
- 正文中的问句行必须用 `### ` 标记为问题标题，以触发 rendered 蓝色样式。
- 正文中的章节标题也必须用 `### ` 标记，确保 rendered 中统一蓝色标题样式。
- 红字、加粗、列表缩进在 rendered 中必须可见。
- 若正文包含图片，必须本地化下载到 `acecamp-raw/assets/<article_id>/`，并在 rendered 中按原文顺序渲染。
- 图片下载失败可回退外链，但必须记录失败日志。

### 3.3 Validation / consistency rules
- `ingest_one.py` 必须执行 source 有效性校验。
- 长文正文长度不得低于阈值（默认 300 字符；长文场景更严格）。
- 入库后 industry/tags 一致性默认以 source 为准。
- 若原文有图片但 rendered 图片数为 0，必须判失败。
- 若原文样式标记在 rendered 丢失，必须判失败。
- 若发布人为“共享调研纪要”，联合发布人规则必须被正确处理。

### 3.4 Runtime safety rules
- 打开详情页或抽取失败时，停止并报告具体错误。
- 不要在失败后默默重试整条 AceCamp 主链。
- 每完成一篇后，关闭新开的 working tab。

## 4) Primary Flows

### 4.1 Single-article flow
Use when one detail page is already open.

Flow:
1. Ensure login state is valid.
2. Run `scripts/ingest_from_open_page.py`.
3. Let it complete:
   - detail extraction
   - source build
   - source-level processing
   - validation
4. Report final artifact paths only after success.

### 4.2 Search / keyword flow
Use when the task starts from a keyword/company/ticker/search intent.

Flow:
1. Ensure login state is valid.
2. Run `scripts/search_and_ingest.py`.
3. Search flow must only keep not-yet-ingested candidates.
4. Delegate each selected article into `scripts/ingest_from_open_page.py`.
5. Close the working tab after each article.

### 4.3 Debug / repair flow
Only use for debugging or repair work.

Flow:
1. `lib/detail_extractor.py`
2. `lib/source_builder.py`
3. `ingest_one.py`

## 5) Required Metadata

Minimum required fields:
- article_id
- 标题
- 内容类型
- 权限
- 标识
- 行业
- 发布时间
- 阅读
- 点赞
- 字数/阅读时长
- VIP状态
- 要点
- 正文（完整）
- 智能追问
- 标签
- 专家简介字段
- 发布人
- 发布人说明
- 联合发布人（若发布人为“共享调研纪要”时重点检查）

## 6) Outputs

For each article, produce all of:
- `acecamp-raw/source/<convention>.md`
- `acecamp-raw/rendered/<convention>.html`
- `acecamp-raw/share/<convention>.pdf`
- `acecamp-raw/index/manifest.jsonl`
- `acecamp-raw/index/索引.xlsx`

Filename convention:
- `文章日期_provider_文章id_文章名_crawl_date`

## 7) Completion Gate

Do not claim completion unless all are true:
- [ ] source written
- [ ] rendered written
- [ ] manifest synced
- [ ] index synced
- [ ] tab closed

If any item fails, do not claim success.
