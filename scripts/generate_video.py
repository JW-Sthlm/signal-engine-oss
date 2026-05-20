"""
generate_video.py: animate an image into an mp4 via Replicate.

Two quality presets:
- cheap (default): bytedance/seedance-2.0-fast at 720p with audio. ~$1 for 10s.
- premium: kwaivgi/kling-v3-omni-video pro (1080p) with audio + reference image
  support. ~$2.20 for 8s. Use for hero posts and character-locked sequences.

Usage:
    python generate_video.py \
        --prompt-file motion.txt \
        --start-image image.png \
        --out clip.mp4 \
        [--quality cheap|premium] \
        [--model <replicate-slug>] \
        [--duration 8] \
        [--aspect-ratio 1:1] \
        [--audio | --no-audio] \
        [--reference-image ref1.png]... \
        [--negative-prompt "blurry, low quality"]

The `--model` flag overrides `--quality`. If you set an unknown model slug, the
script falls back to the generic schema {image, prompt, duration} and ignores
model-specific args (with a warning).

Requires:
    pip install replicate
    REPLICATE_API_TOKEN environment variable (User scope recommended; the Replicate
    Python client reads this name automatically).

Notes:
- Replicate output URLs expire after 1 hour. This script always reads bytes from
  the FileOutput during the run, so the on-disk mp4 is permanent.
- Kling Omni: duration 3-15 s, aspect in {16:9, 9:16, 1:1}, audio on/off, up to
  7 reference images addressable in the prompt as <<<image_1>>>, ...
- Seedance 2.0 Fast: duration 3-12 s, aspect in {16:9, 4:3, 1:1, 3:4, 9:16, 21:9},
  audio on/off, reference images via the [Image1] tag in the prompt.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


QUALITY_PRESETS = {
    "cheap": {
        "model": "bytedance/seedance-2.0-fast",
        "duration": 10,
    },
    "premium": {
        "model": "kwaivgi/kling-v3-omni-video",
        "duration": 8,
    },
}
DEFAULT_QUALITY = "cheap"
DEFAULT_ASPECT = "1:1"
DEFAULT_KLING_MODE = "pro"


def main() -> int:
    ap = argparse.ArgumentParser(description="Animate an image into an mp4 via Replicate (Seedance Fast by default, Kling Omni for premium).")
    ap.add_argument("--prompt-file", type=Path, required=True,
                    help="Path to a text file containing the motion prompt.")
    ap.add_argument("--start-image", type=Path, required=True,
                    help="Reference start image (PNG/JPG). Required.")
    ap.add_argument("--out", type=Path, required=True,
                    help="Path to write the generated .mp4.")
    ap.add_argument("--quality", default=DEFAULT_QUALITY, choices=list(QUALITY_PRESETS.keys()),
                    help="Preset. cheap=Seedance 2.0 Fast (~$1/10s). premium=Kling Omni pro (~$2.20/8s). Default cheap.")
    ap.add_argument("--model", default=None,
                    help="Explicit Replicate model slug. Overrides --quality.")
    ap.add_argument("--duration", type=int, default=None,
                    help="Clip length in seconds. Defaults: cheap=10, premium=8.")
    ap.add_argument("--aspect-ratio", default=DEFAULT_ASPECT, choices=["1:1", "16:9", "9:16"],
                    help="Output aspect ratio. Default 1:1 (matches square thumbnails).")
    ap.add_argument("--mode", default=DEFAULT_KLING_MODE, choices=["standard", "pro"],
                    help="Kling-only quality mode. pro=1080p, standard=720p. Default pro. Ignored by other models.")
    audio_group = ap.add_mutually_exclusive_group()
    audio_group.add_argument("--audio", dest="audio", action="store_true",
                             help="Generate native synced audio (default).")
    audio_group.add_argument("--no-audio", dest="audio", action="store_false",
                             help="Disable native audio.")
    ap.set_defaults(audio=True)
    ap.add_argument("--reference-image", type=Path, action="append", default=[],
                    help="Additional reference image (Kling Omni only, up to 7). Address in prompt as <<<image_N>>>.")
    ap.add_argument("--negative-prompt", default="",
                    help="Optional negative prompt to exclude unwanted content.")
    args = ap.parse_args()

    preset = QUALITY_PRESETS[args.quality]
    model = args.model or preset["model"]
    duration = args.duration if args.duration is not None else preset["duration"]

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN environment variable is not set.", file=sys.stderr)
        print("Set it once with:", file=sys.stderr)
        print('  [Environment]::SetEnvironmentVariable("REPLICATE_API_TOKEN", "<token>", "User")', file=sys.stderr)
        print("Then open a fresh PowerShell window so the variable is loaded.", file=sys.stderr)
        return 2

    if not args.prompt_file.exists():
        print(f"ERROR: prompt file not found: {args.prompt_file}", file=sys.stderr)
        return 2

    prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        print("ERROR: prompt file is empty", file=sys.stderr)
        return 2

    if not args.start_image.exists():
        print(f"ERROR: start image not found: {args.start_image}", file=sys.stderr)
        return 2

    for ref in args.reference_image:
        if not ref.exists():
            print(f"ERROR: reference image not found: {ref}", file=sys.stderr)
            return 2

    if not (3 <= duration <= 15):
        print("ERROR: duration must be between 3 and 15 seconds.", file=sys.stderr)
        return 2

    try:
        import replicate
    except ImportError:
        print("ERROR: replicate package not installed. Run: pip install replicate", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)

    start_fh = open(args.start_image, "rb")
    ref_fhs = [open(p, "rb") for p in args.reference_image]
    try:
        model_input = build_model_input(
            model=model,
            prompt=prompt,
            start_fh=start_fh,
            ref_fhs=ref_fhs,
            duration=duration,
            aspect_ratio=args.aspect_ratio,
            kling_mode=args.mode,
            audio=args.audio,
            negative_prompt=args.negative_prompt,
        )

        print(f"[replicate] model={model} quality={args.quality} duration={duration}s "
              f"aspect={args.aspect_ratio} audio={'on' if args.audio else 'off'} "
              f"refs={len(args.reference_image)}", flush=True)
        print("[replicate] submitting prediction (this typically takes 1-5 minutes)...", flush=True)

        try:
            output = replicate.run(model, input=model_input)
        except Exception as e:
            print(f"ERROR: Replicate API call failed: {e}", file=sys.stderr)
            return 1
    finally:
        start_fh.close()
        for fh in ref_fhs:
            try:
                fh.close()
            except OSError:
                pass

    # Replicate >=1.0 returns FileOutput (or a list of them). Normalise.
    if isinstance(output, list):
        if not output:
            print("ERROR: Replicate returned an empty list.", file=sys.stderr)
            return 1
        file_output = output[0]
    else:
        file_output = output

    # FileOutput exposes .read() (bytes) and .url (str). Fall back to plain bytes/str.
    try:
        if hasattr(file_output, "read"):
            data = file_output.read()
            args.out.write_bytes(data)
        elif isinstance(file_output, (bytes, bytearray)):
            args.out.write_bytes(bytes(file_output))
        elif isinstance(file_output, str) and file_output.startswith("http"):
            import urllib.request
            with urllib.request.urlopen(file_output) as r:
                args.out.write_bytes(r.read())
        else:
            print(f"ERROR: unrecognized Replicate output type: {type(file_output).__name__}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"ERROR: failed to save video bytes: {e}", file=sys.stderr)
        return 1

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"Wrote {args.out} ({size_mb:.2f} MB)")
    return 0


def build_model_input(*, model, prompt, start_fh, ref_fhs, duration, aspect_ratio,
                      kling_mode, audio, negative_prompt):
    """Map common args onto each model's specific input schema."""
    if model.startswith("kwaivgi/kling-v3-omni"):
        if len(ref_fhs) > 7:
            raise SystemExit("ERROR: Kling Omni supports at most 7 reference images.")
        inp = {
            "prompt": prompt,
            "start_image": start_fh,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "mode": kling_mode,
            "generate_audio": audio,
        }
        if ref_fhs:
            inp["reference_images"] = ref_fhs
        if negative_prompt:
            inp["negative_prompt"] = negative_prompt
        return inp

    if model.startswith("bytedance/seedance-2.0"):
        if ref_fhs:
            print(f"WARN: --reference-image ignored by {model} (use --quality premium for multi-ref).", file=sys.stderr)
        # Seedance Fast caps at 720p in our default; resolution kept fixed.
        return {
            "prompt": prompt,
            "image": start_fh,
            "duration": duration,
            "resolution": "720p",
            "aspect_ratio": aspect_ratio,
            "generate_audio": audio,
        }

    if model.startswith("minimax/hailuo-2.3"):
        if ref_fhs:
            print(f"WARN: --reference-image ignored by {model}.", file=sys.stderr)
        if duration not in (6, 10):
            print(f"WARN: Hailuo 2.3 supports duration 6 or 10 only. Got {duration}, clamping to 10.", file=sys.stderr)
            duration = 10
        return {
            "prompt": prompt,
            "first_frame_image": start_fh,
            "duration": duration,
            "resolution": "768p",
        }

    # Generic fallback: try the most common schema.
    print(f"WARN: unknown model {model!r}, using generic schema {{image, prompt, duration}}.", file=sys.stderr)
    if ref_fhs:
        print("WARN: --reference-image ignored by unknown model.", file=sys.stderr)
    return {
        "prompt": prompt,
        "image": start_fh,
        "duration": duration,
    }


if __name__ == "__main__":
    raise SystemExit(main())
