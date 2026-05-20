"""
generate_image.py - render a 1:1 image via OpenAI Image 2 (gpt-image-2).

Two paths:
  1. Portrait composite + edit (default when 1+ portraits supplied):
     stitches portraits onto a neutral canvas, then images.edit() generates
     the final composition around them. Better facial likeness.
  2. Pure text-to-image (when no portraits supplied or --no-composite):
     images.generate() with the prompt only. Faster, weaker face fidelity.

Usage:
    python generate_image.py --prompt-file prompt.txt --out image.png \
        [--portrait person.jpg] [--model gpt-image-2] \
        [--size 1024x1024] [--quality high] [--no-composite]

Requires:
    pip install openai pillow
    OPENAI_API_KEY environment variable
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--portrait", type=Path, action="append", default=[],
                    help="Reference portrait (repeatable). Used to build a composite input image.")
    ap.add_argument("--model", default="gpt-image-2",
                    help="OpenAI image model. Default gpt-image-2 (current best). Older: gpt-image-1.")
    ap.add_argument("--size", default="1024x1024",
                    help="Output size. 1024x1024, 1024x1536, 1536x1024.")
    ap.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"],
                    help="Quality tier. high recommended for poster output. Cost scales accordingly.")
    ap.add_argument("--no-composite", action="store_true",
                    help="Skip the portrait-composite step, use pure text-to-image generate().")
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set", file=sys.stderr)
        return 2

    if not args.prompt_file.exists():
        print(f"ERROR: prompt file not found: {args.prompt_file}", file=sys.stderr)
        return 2

    prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        print("ERROR: prompt file is empty", file=sys.stderr)
        return 2

    missing = [p for p in args.portrait if not p.exists()]
    if missing:
        print(f"ERROR: portrait file(s) not found: {missing}", file=sys.stderr)
        return 2

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai", file=sys.stderr)
        return 2

    client = OpenAI(api_key=api_key)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    use_composite = bool(args.portrait) and not args.no_composite

    try:
        if use_composite:
            print(f"[openai] using portrait composite path with {len(args.portrait)} portrait(s)")
            composite_path = _build_composite(args.portrait)
            try:
                with open(composite_path, "rb") as f:
                    response = client.images.edit(
                        model=args.model,
                        image=f,
                        prompt=prompt,
                        size=args.size,
                        quality=args.quality,
                    )
            finally:
                try:
                    composite_path.unlink()
                except OSError:
                    pass
        else:
            print(f"[openai] using pure text-to-image path (model={args.model}, size={args.size}, quality={args.quality})")
            response = client.images.generate(
                model=args.model,
                prompt=prompt,
                size=args.size,
                quality=args.quality,
            )
    except Exception as e:
        print(f"ERROR: OpenAI API call failed: {e}", file=sys.stderr)
        return 1

    data = response.data[0] if response.data else None
    if not data:
        print("ERROR: OpenAI response had no data", file=sys.stderr)
        return 1

    if getattr(data, "b64_json", None):
        args.out.write_bytes(base64.b64decode(data.b64_json))
    elif getattr(data, "url", None):
        import urllib.request
        with urllib.request.urlopen(data.url) as r:
            args.out.write_bytes(r.read())
    else:
        print("ERROR: OpenAI response had neither b64_json nor url", file=sys.stderr)
        return 1

    print(f"Wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


def _build_composite(portraits: list[Path]) -> Path:
    """Stitch portraits side-by-side onto a neutral 1024x1024 canvas.

    Returns path to a temp PNG. Caller must unlink after use.
    """
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: pillow required for composite path. Run: pip install pillow", file=sys.stderr)
        raise

    canvas = Image.new("RGB", (1024, 1024), (24, 24, 28))
    n = len(portraits)
    if n == 0:
        raise ValueError("no portraits")

    cell_w = 1024 // n
    cell_h = 1024
    for i, p in enumerate(portraits):
        img = Image.open(p).convert("RGB")
        scale = min(cell_w / img.width, cell_h / img.height)
        new_w = max(1, int(img.width * scale))
        new_h = max(1, int(img.height * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        x = i * cell_w + (cell_w - new_w) // 2
        y = (cell_h - new_h) // 2
        canvas.paste(img, (x, y))

    fd, path = tempfile.mkstemp(suffix=".png", prefix="composite_")
    os.close(fd)
    out = Path(path)
    canvas.save(out, "PNG")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
