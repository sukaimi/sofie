#!/usr/bin/env python3
"""Black-box end-to-end smoke test for a running SOFIE deployment.

Drives ONE brief all the way through the live system without a browser:
upload -> WebSocket brief_uploaded -> confirm -> pipeline -> (optional
operator approve) -> download the composited JPEG and verify it.

This talks only to the public HTTP API + chat WebSocket; it does not import
or modify any application code. Handy as a post-deploy smoke check.

Usage:
    python scripts/prod_e2e_smoke.py [BRIEF.docx] [--base URL] [--approve]

    BRIEF.docx   Path to a .docx brief with LIVE asset links. Defaults to
                 tests/test_brief.docx (NOTE: that fixture uses example.com
                 placeholder URLs that 404, so Ray correctly blocks it before
                 an image is produced — pass a brief with real assets to get
                 a full render).
    --base URL   Deployment base URL. Default: https://sofie.codeandcraft.ai
    --approve    Auto-approve the operator-review step so the job delivers.
                 Omit to stop at review and just report the job_id.

Requires: requests, websockets, certifi (all in the project venv).
Exit code 0 = brief reached a verified downloadable JPEG (or, without
--approve, reached operator review cleanly).
"""
import argparse
import asyncio
import json
import ssl
import time
import uuid
from pathlib import Path

import certifi
import requests
import websockets

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://sofie.codeandcraft.ai"
DEFAULT_BRIEF = REPO_ROOT / "tests" / "test_brief.docx"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TOTAL_TIMEOUT = 12 * 60  # seconds — allow for hero-image generation + multiple sizes
SSL_CTX = ssl.create_default_context(cafile=certifi.where())  # websockets needs an explicit CA bundle


def _api(base, method, path, **kwargs):
    resp = requests.request(method, base + path, timeout=60, **kwargs)
    print(f"HTTP {method} {path} -> {resp.status_code}", flush=True)
    return resp


def _jpeg_paths(output_paths):
    """output_paths comes back as {"1080x1080": "/app/output/<job>/composited_...jpg"}."""
    values = output_paths.values() if isinstance(output_paths, dict) else (output_paths or [])
    return [p for p in values if str(p).lower().endswith((".jpg", ".jpeg"))]


async def drive(base, brief, approve):
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    if not brief.is_file():
        raise FileNotFoundError(brief)

    with brief.open("rb") as handle:
        uploaded = _api(base, "POST", "/api/upload-brief",
                        files={"file": (brief.name, handle, DOCX_MIME)})
    uploaded.raise_for_status()
    upload = uploaded.json()
    print("UPLOAD " + json.dumps(upload), flush=True)

    conversation_id = uuid.uuid4().hex
    job_id, output_paths, confirmed = None, {}, False
    started = time.monotonic()

    async with websockets.connect(f"{ws_base}/ws/{conversation_id}", ssl=SSL_CTX,
                                  open_timeout=30, ping_interval=20,
                                  ping_timeout=30, close_timeout=10) as ws:
        await ws.send(json.dumps({"type": "brief_uploaded",
                                  "content": upload["filename"],
                                  "metadata": {"file_path": upload["file_path"]}}))
        print(f"WS connected conversation={conversation_id}; brief_uploaded sent", flush=True)

        while time.monotonic() - started < TOTAL_TIMEOUT:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=45)
            except asyncio.TimeoutError:
                continue
            message = json.loads(raw)
            print("WS " + json.dumps(message, ensure_ascii=False), flush=True)
            if message.get("job_id"):
                job_id = message["job_id"]
            meta = message.get("metadata") or {}
            if meta.get("output_paths"):
                output_paths = meta["output_paths"]
            if not confirmed and message.get("role") == "sofie" \
                    and "Is this all correct?" in message.get("content", ""):
                await ws.send(json.dumps({"type": "confirmation",
                                          "content": "Yes, that's correct", "metadata": {}}))
                confirmed = True
                print("WS confirmation sent", flush=True)
            if message.get("type") == "image" and output_paths:
                break

    if not job_id:
        raise RuntimeError("No job_id observed — brief was likely rejected before a job was created")

    final_status = _api(base, "GET", f"/api/job/{job_id}/status").json().get("status", "unknown")

    if not output_paths:
        listing = _api(base, "GET", "/api/operator/jobs")
        if listing.ok:
            match = next((j for j in listing.json() if j.get("job_id") == job_id), None)
            if match:
                output_paths = match.get("output_paths") or {}
                final_status = match.get("status", final_status)

    auto_approved = False
    if approve and final_status in {"operator_review", "review", "escalated"}:
        approval = _api(base, "POST", f"/api/operator/jobs/{job_id}/approve")
        approval.raise_for_status()
        auto_approved = True
        final_status = approval.json().get("status", "approved")

    jpg_paths = _jpeg_paths(output_paths)
    if not jpg_paths:
        print(json.dumps({"job_id": job_id, "final_status": final_status,
                          "output_paths": output_paths,
                          "note": "no JPEG output (brief blocked, or not approved)"}, indent=2))
        return final_status in {"operator_review", "review"}  # clean stop-at-review counts as pass

    filename = Path(jpg_paths[0]).name
    dl = _api(base, "GET", f"/api/job/{job_id}/download/{filename}")
    local = REPO_ROOT / f"{job_id}_{filename}"
    local.write_bytes(dl.content)
    ctype = dl.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    passed = (dl.status_code == 200 and ctype == "image/jpeg"
              and "attachment" in dl.headers.get("Content-Disposition", "").lower()
              and dl.content[:3] == b"\xff\xd8\xff")
    print("RESULT " + json.dumps({
        "job_id": job_id, "final_status": final_status, "auto_approved": auto_approved,
        "output_paths": output_paths,
        "download": {"http_status": dl.status_code, "content_type": dl.headers.get("Content-Type"),
                     "content_disposition": dl.headers.get("Content-Disposition"),
                     "byte_size": len(dl.content), "jpeg_magic_pass": dl.content[:3] == b"\xff\xd8\xff"},
        "verification_pass": passed, "local_path": str(local),
    }, indent=2), flush=True)
    return passed


def main():
    parser = argparse.ArgumentParser(description="SOFIE end-to-end smoke test")
    parser.add_argument("brief", nargs="?", default=str(DEFAULT_BRIEF),
                        help="Path to a .docx brief (needs LIVE asset links for a full render)")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Deployment base URL")
    parser.add_argument("--approve", action="store_true", help="Auto-approve operator review")
    args = parser.parse_args()
    ok = asyncio.run(drive(args.base.rstrip("/"), Path(args.brief), args.approve))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
