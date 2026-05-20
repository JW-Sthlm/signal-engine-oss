"""
linkedin_post.py: push a polished post to LinkedIn as a draft (default) or live.

Uses LinkedIn's REST Posts API with `lifecycleState: DRAFT` so the post lands in
your LinkedIn drafts tab. You review and publish from the LinkedIn UI.

Why drafts and not direct publish:
- LinkedIn's API has no "preview-then-confirm" UI. Drafts are the safe path.
- You see the post rendered in LinkedIn's real composer before it goes out.
- Same one-click publish, zero risk of pushing a typo.

Use --publish to skip the draft step and go live immediately.

Usage:
    # Push to drafts (default, safe)
    python scripts/linkedin_post.py --post _workdir/posts/my-post.md

    # Push to drafts with an image
    python scripts/linkedin_post.py --post _workdir/posts/my-post.md \
        --image _workdir/images/my-post.png

    # Skip drafts, publish live
    python scripts/linkedin_post.py --post _workdir/posts/my-post.md --publish

Requires:
    pip install httpx
    LINKEDIN_ACCESS_TOKEN environment variable (run linkedin_auth.py once)
    LINKEDIN_AUTHOR_URN environment variable (set by linkedin_auth.py)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# LinkedIn API version — bump this if LinkedIn deprecates the current one.
# See https://learn.microsoft.com/en-us/linkedin/marketing/versioning
LINKEDIN_API_VERSION = "202405"

POSTS_ENDPOINT = "https://api.linkedin.com/rest/posts"
ASSETS_REGISTER_ENDPOINT = "https://api.linkedin.com/v2/assets?action=registerUpload"


def _read_post(path: Path) -> str:
    if not path.exists():
        print(f"ERROR: post file not found: {path}", file=sys.stderr)
        sys.exit(2)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        print(f"ERROR: post file is empty: {path}", file=sys.stderr)
        sys.exit(2)
    return text


def _upload_image(image_path: Path, token: str, author_urn: str) -> str:
    """Register an upload, PUT the bytes, return the asset URN."""
    print(f"[linkedin] registering image upload: {image_path.name}")
    register_body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    r = httpx.post(ASSETS_REGISTER_ENDPOINT, headers=headers, json=register_body, timeout=30)
    if r.status_code >= 400:
        print(f"ERROR: assets register failed ({r.status_code}): {r.text}", file=sys.stderr)
        sys.exit(1)
    data = r.json()["value"]
    asset_urn = data["asset"]
    upload_url = data["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]["uploadUrl"]

    print(f"[linkedin] uploading {image_path.stat().st_size} bytes")
    with image_path.open("rb") as f:
        r = httpx.put(
            upload_url,
            content=f.read(),
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    if r.status_code >= 400:
        print(f"ERROR: image upload failed ({r.status_code}): {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"[linkedin] image asset: {asset_urn}")
    return asset_urn


def _build_post_body(
    text: str,
    author_urn: str,
    *,
    lifecycle: str,
    image_asset: str | None = None,
    image_alt: str = "",
) -> dict:
    body: dict = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": lifecycle,
        "isReshareDisabledByAuthor": False,
    }
    if image_asset:
        body["content"] = {
            "media": {
                "id": image_asset,
                "altText": image_alt or "Generated image",
            }
        }
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", type=Path, required=True,
                    help="Path to the polished post markdown file.")
    ap.add_argument("--image", type=Path, default=None,
                    help="Optional path to an image to attach.")
    ap.add_argument("--alt", default="",
                    help="Alt text for the image (accessibility).")
    ap.add_argument("--publish", action="store_true",
                    help="Publish live instead of saving to drafts. Default is drafts.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build and print the request body, do not actually call LinkedIn.")
    args = ap.parse_args()

    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    author_urn = os.environ.get("LINKEDIN_AUTHOR_URN")

    if not args.dry_run:
        if not token:
            print(
                "ERROR: LINKEDIN_ACCESS_TOKEN not set. Run scripts/linkedin_auth.py once.",
                file=sys.stderr,
            )
            return 2
        if not author_urn:
            print(
                "ERROR: LINKEDIN_AUTHOR_URN not set. Run scripts/linkedin_auth.py once.",
                file=sys.stderr,
            )
            return 2
    else:
        token = token or "DRY-RUN-TOKEN"
        author_urn = author_urn or "urn:li:person:DRY-RUN"

    text = _read_post(args.post)
    if len(text) > 3000:
        print(
            f"WARNING: post is {len(text)} chars. LinkedIn caps at 3000. Truncating.",
            file=sys.stderr,
        )
        text = text[:3000]

    image_asset = None
    if args.image:
        if not args.image.exists():
            print(f"ERROR: image not found: {args.image}", file=sys.stderr)
            return 2
        if args.dry_run:
            image_asset = "urn:li:image:DRY-RUN"
            print(f"[dry-run] would upload {args.image}")
        else:
            image_asset = _upload_image(args.image, token, author_urn)

    lifecycle = "PUBLISHED" if args.publish else "DRAFT"
    body = _build_post_body(
        text,
        author_urn,
        lifecycle=lifecycle,
        image_asset=image_asset,
        image_alt=args.alt,
    )

    if args.dry_run:
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return 0

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    action_word = "publishing live" if args.publish else "saving to drafts"
    print(f"[linkedin] {action_word}: {len(text)} chars, image={'yes' if image_asset else 'no'}")
    r = httpx.post(POSTS_ENDPOINT, headers=headers, json=body, timeout=30)
    if r.status_code >= 400:
        print(f"ERROR: post failed ({r.status_code}): {r.text}", file=sys.stderr)
        return 1

    post_urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id") or "(unknown)"
    if args.publish:
        print(f"[linkedin] PUBLISHED. Post URN: {post_urn}")
        print("Open https://www.linkedin.com/feed/ to see it.")
    else:
        print(f"[linkedin] DRAFT saved. Post URN: {post_urn}")
        print("Open https://www.linkedin.com/post/new/ — your draft is in the composer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
