"""
Fetch Z80 binary analysis reference material from external sources.

Sources:
  - sp00nznet/zxrecomp (MIT) — static recompilation toolkit
  - cormacj/z80-smart-disassembler (GPL-2.0) — smart disassembler
  - sharkcz/z80dasm (GPL-2.0) — classic Z80 disassembler
  - mrcook.uk reverse engineering walkthrough (community/open)
"""

import logging
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_DIR = Path(__file__).parent.parent / "raw" / "z80" / "binary_analysis"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; knowledge-corpus-fetcher/1.0)"
}
TIMEOUT = 15
SLEEP = 1

CATEGORY = "z80-binary-analysis"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers (same pattern as fetch_z80_extras.py)
# ---------------------------------------------------------------------------

def get(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except requests.HTTPError as exc:
        log.error("HTTP %s fetching %s — skipping", exc.response.status_code, url)
    except requests.RequestException as exc:
        log.error("Request failed for %s: %s — skipping", url, exc)
    return None


def frontmatter(topic: str, source_url: str, licence: str, tags: list[str]) -> str:
    tag_str = ", ".join(tags)
    return (
        "---\n"
        f'topic: "{topic}"\n'
        f"category: {CATEGORY}\n"
        f'source_url: "{source_url}"\n'
        f'licence: "{licence}"\n'
        f"tags: [{tag_str}]\n"
        "---\n"
    )


def write_raw(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log.info("Wrote %s (%d words)", path, len(content.split()))


def strip_badges(md: str) -> str:
    """Remove markdown badge images and HTML comments from README content."""
    md = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", md)
    md = re.sub(r"!\[.*?\]\(.*?\)", "", md)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)
    return md.strip()


# ---------------------------------------------------------------------------
# Source 1: zxrecomp (MIT)
# ---------------------------------------------------------------------------

ZXRECOMP_URL = "https://raw.githubusercontent.com/sp00nznet/zxrecomp/main/README.md"
ZXRECOMP_REPO = "https://github.com/sp00nznet/zxrecomp"


def fetch_zxrecomp() -> None:
    log.info("Fetching zxrecomp README...")
    text = get(ZXRECOMP_URL)
    if not text:
        return

    body = strip_badges(text)
    # Strip the H1 title — will be the topic
    body = re.sub(r"^# .+\n*", "", body).strip()

    fm = frontmatter(
        topic="zxrecomp — Z80 Static Recompilation Toolkit",
        source_url=ZXRECOMP_REPO,
        licence="MIT",
        tags=["z80", "binary-analysis", "recompilation", "disassembly", "spectrum"],
    )
    content = fm + "\n" + body + "\n"
    write_raw(RAW_DIR / "zxrecomp.md", content)


# ---------------------------------------------------------------------------
# Source 2: z80-smart-disassembler (GPL-2.0)
# ---------------------------------------------------------------------------

SMART_DISASM_URL = "https://raw.githubusercontent.com/cormacj/z80-smart-disassembler/main/README.md"
SMART_DISASM_REPO = "https://github.com/cormacj/z80-smart-disassembler"


def fetch_smart_disassembler() -> None:
    log.info("Fetching z80-smart-disassembler README...")
    text = get(SMART_DISASM_URL)
    if not text:
        return

    body = strip_badges(text)
    body = re.sub(r"^# .+\n*", "", body).strip()

    fm = frontmatter(
        topic="z80-smart-disassembler — Automatic Label and Data Area Detection",
        source_url=SMART_DISASM_REPO,
        licence="GPL-2.0",
        tags=["z80", "binary-analysis", "disassembler", "labels", "data-detection"],
    )
    content = fm + "\n" + body + "\n"
    write_raw(RAW_DIR / "z80-smart-disassembler.md", content)


# ---------------------------------------------------------------------------
# Source 3: z80dasm (GPL-2.0)
# ---------------------------------------------------------------------------

Z80DASM_URL = "https://raw.githubusercontent.com/sharkcz/z80dasm/master/README"
Z80DASM_REPO = "https://github.com/sharkcz/z80dasm"


def fetch_z80dasm() -> None:
    log.info("Fetching z80dasm README...")
    text = get(Z80DASM_URL)
    if not text:
        return

    body = text.strip()

    fm = frontmatter(
        topic="z80dasm — Z80 Disassembler with Control File Support",
        source_url=Z80DASM_REPO,
        licence="GPL-2.0",
        tags=["z80", "binary-analysis", "disassembler", "control-file", "spectrum"],
    )
    content = fm + "\n" + body + "\n"
    write_raw(RAW_DIR / "z80dasm.md", content)


# ---------------------------------------------------------------------------
# Source 4: mrcook.uk reverse engineering walkthrough
# ---------------------------------------------------------------------------

MRCOOK_URL = "https://mrcook.uk/reverse-engineering-zx-spectrum-games/"
MRCOOK_REPO = "https://mrcook.uk/reverse-engineering-zx-spectrum-games/"


def fetch_mrcook() -> None:
    log.info("Fetching mrcook reverse engineering article...")
    html = get(MRCOOK_URL)
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    article = soup.find(class_="post-content") or soup.find("article")
    if not article:
        log.error("Could not find article content on mrcook page")
        return

    # Extract text content, preserving structure
    lines: list[str] = []
    for el in article.children:
        tag = getattr(el, "name", None)
        if not hasattr(el, "get_text"):
            continue
        text = " ".join(el.get_text(separator=" ").split())
        if not text:
            continue

        if tag in ("h2", "h3"):
            prefix = "## " if tag == "h2" else "### "
            lines.append(f"\n{prefix}{text}\n")
        elif tag == "pre":
            code = el.get_text()
            lines.append(f"\n```\n{code}\n```\n")
        elif tag == "ul":
            for li in el.find_all("li"):
                lines.append(f"- {' '.join(li.get_text(separator=' ').split())}")
        elif tag == "ol":
            for i, li in enumerate(el.find_all("li"), 1):
                lines.append(f"{i}. {' '.join(li.get_text(separator=' ').split())}")
        elif tag == "p":
            lines.append(text)
        elif tag == "figure":
            continue
        else:
            if text:
                lines.append(text)

    body = "\n\n".join(lines).strip()
    # Fix whitespace before punctuation left by inline element extraction
    body = re.sub(r" ([;:,.\?\!])", r"\1", body)

    fm = frontmatter(
        topic="Reverse Engineering ZX Spectrum Games — Walkthrough",
        source_url=MRCOOK_URL,
        licence="community/open",
        tags=["z80", "binary-analysis", "reverse-engineering", "skoolkit", "spectrum"],
    )
    content = fm + "\n" + body + "\n"
    write_raw(RAW_DIR / "mrcook-reverse-engineering.md", content)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    fetched = 0

    fetch_zxrecomp()
    fetched += 1
    time.sleep(SLEEP)

    fetch_smart_disassembler()
    fetched += 1
    time.sleep(SLEEP)

    fetch_z80dasm()
    fetched += 1
    time.sleep(SLEEP)

    fetch_mrcook()
    fetched += 1

    log.info("Done — fetched %d sources to %s", fetched, RAW_DIR)


if __name__ == "__main__":
    main()
