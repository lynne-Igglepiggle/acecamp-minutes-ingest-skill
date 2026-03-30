#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path


def staged_files():
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
    if p.returncode != 0:
        return []
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def check_file(path: Path):
    txt = path.read_text(encoding="utf-8")
    if "## 三、正文" not in txt:
        return f"{path}: missing section ## 三、正文"

    m_words = re.search(r"本文共(\d+)字", txt)
    expected_words = int(m_words.group(1)) if m_words else None

    i = txt.find("## 三、正文")
    j = txt.find("## 四、智能追问", i + 1)
    body = txt[i:j if j > 0 else len(txt)].strip()
    no_ws = re.sub(r"\s+", "", body)

    if not body:
        return f"{path}: empty body"
    if any(x in body for x in ["未展示", "暂无正文", "待补充"]) and len(no_ws) < 60:
        return f"{path}: placeholder-only body"
    if len(no_ws) < 300 and (expected_words is None or expected_words >= 800):
        return f"{path}: body too short ({len(no_ws)}) for long article"

    return None


def main():
    files = staged_files()
    targets = [Path(f) for f in files if f.startswith("acecamp-raw/source/") and f.endswith(".md")]
    errs = []
    for p in targets:
        if p.exists():
            e = check_file(p)
            if e:
                errs.append(e)

    if errs:
        print("PRE-COMMIT FAIL: source body validation failed")
        for e in errs:
            print(" -", e)
        sys.exit(1)

    print("PRE-COMMIT PASS: source body validation")


if __name__ == "__main__":
    main()
