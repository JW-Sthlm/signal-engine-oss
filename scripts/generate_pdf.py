"""Generate a LinkedIn-ready carousel PDF from a polished post.

Input:  _workdir/posts/<slug>.md   (the post body in markdown)
Output: _workdir/pdfs/<slug>.pdf   (square multi-page PDF, 1080x1080 logical)

Why this exists: LinkedIn document posts (PDF carousels) get materially more
reach than plain text. This script turns one polished post into a swipeable
carousel without leaving the signal-engine flow.

How it works:
- Page 1 is a cover with the post's opening line as the hook.
- Each subsequent page holds one paragraph in large readable type.
- Max 8 content pages so the carousel stays snackable.
- Final page is a soft CTA (configurable, defaults to a generic line).

No external API. fpdf2 only. Free.

Usage:
    python scripts/generate_pdf.py --post _workdir/posts/<slug>.md
    python scripts/generate_pdf.py --post path/to/post.md --cta "yourname.com"
    python scripts/generate_pdf.py --post path/to/post.md --theme light
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("[pdf] fpdf2 not installed. Run: pip install fpdf2", file=sys.stderr)
    sys.exit(1)


PAGE_SIZE_MM = 285.75
MARGIN_MM = 28
MAX_BODY_PAGES = 8

_UNICODE_FALLBACKS = {
    "\u2192": "->",   # right arrow
    "\u2190": "<-",   # left arrow
    "\u2014": "--",   # em dash (banned in voice anyway, but in case)
    "\u2013": "-",    # en dash
    "\u2026": "...",  # ellipsis
    "\u00b7": "*",    # middle dot
    "\u2022": "*",    # bullet
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u00a0": " ",
}


def _ascii_safe(text: str) -> str:
    """Coerce common unicode glyphs to ASCII for fpdf core fonts.

    Core PDF fonts (Helvetica) cannot render most Unicode. Rather than ship
    a TTF, replace the small set of glyphs that show up in polished posts.
    """
    for src, dst in _UNICODE_FALLBACKS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")

THEMES = {
    "dark": {
        "bg": (15, 13, 31),
        "fg": (244, 243, 255),
        "accent": (249, 115, 22),
        "muted": (169, 166, 207),
    },
    "light": {
        "bg": (252, 252, 250),
        "fg": (24, 22, 40),
        "accent": (190, 24, 93),
        "muted": (120, 117, 158),
    },
}


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def _split_paragraphs(post: str) -> list[str]:
    body = _strip_frontmatter(post.strip())
    # Drop a leading H1 / H2 header if present — covers are built from the hook.
    body = re.sub(r"^#{1,6}\s+[^\n]*\n+", "", body, count=1)
    raw_paras = re.split(r"\n\s*\n+", body)
    cleaned: list[str] = []
    for p in raw_paras:
        para = " ".join(line.strip() for line in p.splitlines() if line.strip())
        if not para:
            continue
        cleaned.append(para)
    return cleaned


def _measure_lines(pdf: FPDF, text: str, width: float, line_h: float) -> int:
    try:
        result = pdf.multi_cell(w=width, h=line_h, text=text, align="L",
                                dry_run=True, output="LINES")
    except TypeError:
        try:
            result = pdf.multi_cell(w=width, h=line_h, text=text, align="L",
                                    split_only=True)
        except TypeError:
            result = pdf.multi_cell(w=width, h=line_h, txt=text, align="L",
                                    split_only=True)
    return len(result)


def _fit_font_size(pdf: FPDF, text: str, max_width_mm: float, max_height_mm: float,
                   start_pt: int, min_pt: int, line_height_factor: float = 1.18) -> int:
    """Find the largest font size where the text fits in the box."""
    for size in range(start_pt, min_pt - 1, -2):
        pdf.set_font_size(size)
        line_h_mm = size * line_height_factor * 0.3528
        n_lines = _measure_lines(pdf, text, max_width_mm, line_h_mm)
        total_h = n_lines * line_h_mm
        if total_h <= max_height_mm:
            return size
    return min_pt


def _draw_background(pdf: FPDF, theme: dict) -> None:
    pdf.set_fill_color(*theme["bg"])
    pdf.rect(0, 0, PAGE_SIZE_MM, PAGE_SIZE_MM, "F")


def _write_text(pdf: FPDF, x: float, y: float, w: float, text: str,
                color: tuple[int, int, int], align: str = "L",
                line_height_factor: float = 1.18) -> None:
    pdf.set_xy(x, y)
    pdf.set_text_color(*color)
    size = pdf.font_size_pt
    line_h_mm = size * line_height_factor * 0.3528
    try:
        pdf.multi_cell(w=w, h=line_h_mm, text=text, align=align)
    except TypeError:
        pdf.multi_cell(w=w, h=line_h_mm, txt=text, align=align)


def _add_cover(pdf: FPDF, theme: dict, brand: str, hook: str) -> None:
    hook = _ascii_safe(hook)
    brand = _ascii_safe(brand)
    pdf.add_page()
    _draw_background(pdf, theme)

    pdf.set_font("Helvetica", "B", 11)
    _write_text(pdf, MARGIN_MM, MARGIN_MM, PAGE_SIZE_MM - 2 * MARGIN_MM,
                brand.upper(), theme["accent"], "L")

    available_w = PAGE_SIZE_MM - 2 * MARGIN_MM
    available_h = PAGE_SIZE_MM - 2 * MARGIN_MM - 60
    pdf.set_font("Helvetica", "B", 60)
    size = _fit_font_size(pdf, hook, available_w, available_h, 64, 28, 1.1)
    pdf.set_font("Helvetica", "B", size)
    line_h_mm = size * 1.1 * 0.3528
    n_lines = _measure_lines(pdf, hook, available_w, line_h_mm)
    total_h = n_lines * line_h_mm
    y_start = (PAGE_SIZE_MM - total_h) / 2
    _write_text(pdf, MARGIN_MM, y_start, available_w, hook,
                theme["fg"], "L", 1.1)

    pdf.set_font("Helvetica", "", 14)
    _write_text(pdf, MARGIN_MM, PAGE_SIZE_MM - MARGIN_MM - 8,
                PAGE_SIZE_MM - 2 * MARGIN_MM,
                "swipe ->", theme["muted"], "L")


def _add_body_page(pdf: FPDF, theme: dict, paragraph: str, page_num: int,
                   total_pages: int) -> None:
    paragraph = _ascii_safe(paragraph)
    pdf.add_page()
    _draw_background(pdf, theme)

    available_w = PAGE_SIZE_MM - 2 * MARGIN_MM
    available_h = PAGE_SIZE_MM - 2 * MARGIN_MM - 30
    pdf.set_font("Helvetica", "", 40)
    size = _fit_font_size(pdf, paragraph, available_w, available_h, 40, 20, 1.25)
    pdf.set_font("Helvetica", "", size)
    line_h_mm = size * 1.25 * 0.3528
    n_lines = _measure_lines(pdf, paragraph, available_w, line_h_mm)
    total_h = n_lines * line_h_mm
    y_start = (PAGE_SIZE_MM - total_h) / 2
    _write_text(pdf, MARGIN_MM, y_start, available_w, paragraph,
                theme["fg"], "L", 1.25)

    pdf.set_font("Helvetica", "", 11)
    _write_text(pdf, MARGIN_MM, PAGE_SIZE_MM - MARGIN_MM - 6,
                PAGE_SIZE_MM - 2 * MARGIN_MM,
                f"{page_num} / {total_pages}", theme["muted"], "L")


def _add_cta(pdf: FPDF, theme: dict, cta_line: str, cta_url: str) -> None:
    cta_line = _ascii_safe(cta_line)
    cta_url = _ascii_safe(cta_url)
    pdf.add_page()
    _draw_background(pdf, theme)

    available_w = PAGE_SIZE_MM - 2 * MARGIN_MM
    pdf.set_font("Helvetica", "B", 48)
    _write_text(pdf, MARGIN_MM, PAGE_SIZE_MM / 2 - 40, available_w,
                cta_line, theme["fg"], "L", 1.15)

    pdf.set_font("Helvetica", "", 22)
    _write_text(pdf, MARGIN_MM, PAGE_SIZE_MM / 2 + 30, available_w,
                cta_url, theme["accent"], "L")


def build_pdf(post_path: Path, output_path: Path, *, brand: str = "signal",
              cta_line: str = "Built with signal-engine.",
              cta_url: str = "github.com/JW-Sthlm/signal-engine",
              theme: str = "dark") -> Path:
    text = post_path.read_text(encoding="utf-8")
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        raise ValueError(f"No content found in {post_path}")

    hook = paragraphs[0]
    body_paragraphs = paragraphs[1 : 1 + MAX_BODY_PAGES]
    total_pages = 1 + len(body_paragraphs) + 1

    palette = THEMES.get(theme, THEMES["dark"])
    pdf = FPDF(orientation="P", unit="mm", format=(PAGE_SIZE_MM, PAGE_SIZE_MM))
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)

    _add_cover(pdf, palette, brand, hook)
    for i, para in enumerate(body_paragraphs, start=2):
        _add_body_page(pdf, palette, para, i, total_pages)
    _add_cta(pdf, palette, cta_line, cta_url)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post", required=True, help="Path to a polished post markdown file.")
    parser.add_argument("--out", default=None,
                        help="Output PDF path. Defaults to _workdir/pdfs/<slug>.pdf next to the post.")
    parser.add_argument("--brand", default=os.environ.get("SIGNAL_BRAND", "signal"),
                        help="Small brand label on the cover page (default: 'signal').")
    parser.add_argument("--cta-line", default=os.environ.get("SIGNAL_CTA_LINE", "Built with signal-engine."))
    parser.add_argument("--cta-url", default=os.environ.get("SIGNAL_CTA_URL", "github.com/JW-Sthlm/signal-engine"))
    parser.add_argument("--theme", choices=["dark", "light"], default=os.environ.get("SIGNAL_PDF_THEME", "dark"))
    args = parser.parse_args()

    post_path = Path(args.post)
    if not post_path.exists():
        print(f"[pdf] Post not found: {post_path}", file=sys.stderr)
        return 1

    if args.out:
        output_path = Path(args.out)
    else:
        slug = post_path.stem
        output_path = post_path.parent.parent / "pdfs" / f"{slug}.pdf"

    try:
        result = build_pdf(post_path, output_path, brand=args.brand,
                          cta_line=args.cta_line, cta_url=args.cta_url,
                          theme=args.theme)
    except Exception as exc:
        print(f"[pdf] Failed: {exc}", file=sys.stderr)
        return 2

    print(f"[pdf] Wrote {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
