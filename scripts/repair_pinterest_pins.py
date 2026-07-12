import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, "/var/www/mathrelaxing.store")

from database import SessionLocal
from models.pinterest_pin import PinterestPin
from routers import pinterest as pin_api


ROOT = Path("/var/www/mathrelaxing.store")
PUBLIC_BASE = "https://mathrelaxing.store"
COVER_DIR = ROOT / "static/covers/pinterest-repairs"
COVER_DIR.mkdir(parents=True, exist_ok=True)


REPLACEMENTS = [
    {
        "slug": "chladni-figures-loop-pack",
        "title": "Chladni Figures: Cymatic Geometry Loop",
        "video": "static/videos/chladni_spin1_1080p30.mp4",
        "delete": ["927037904566871234"],
        "seek": "00:00:04",
    },
    {
        "slug": "voronoi-organics-loop-pack",
        "title": "Voronoi Organic Cells: Mathematical Loop",
        "video": "static/videos/voronoi_hue1_1080p30.mp4",
        "delete": ["927037904566871142"],
        "seek": "00:00:03",
    },
    {
        "slug": "harmonic-geometry-loop-pack",
        "title": "Harmonic Geometry: Lissajous Motion Loop",
        "video": "static/videos/harmonic_hue3_1080p30.mp4",
        "delete": ["927037904566870772"],
        "seek": "00:00:03",
    },
    {
        "slug": "strange-attractors-loop-pack",
        "title": "Lorenz Flow: Strange Attractor Animation",
        "video": "static/videos/lorenz_flow_1080p30.mp4",
        "delete": ["927037904566870644", "927037904566389266"],
        "seek": "00:00:05",
    },
    {
        "slug": "complex-plane-loop-pack",
        "title": "Mobius Spin: Complex Plane Animation",
        "video": "static/videos/mobius_spin_1080p30.mp4",
        "delete": ["927037904566786226"],
        "seek": "00:00:04",
    },
    {
        "slug": "radial-symmetry-loop-pack",
        "title": "Rose Curve Spin: Radial Symmetry Loop",
        "video": "static/videos/rose_spin_1080p30.mp4",
        "delete": ["927037904566786223"],
        "seek": "00:00:04",
    },
]

DELETE_ONLY = [
    "927037904566988894",  # blank desk mat preview
    "927037904566871066",  # old Turing preview, newer dynamic pin exists
    "927037904566354524",  # old particle preview, newer better pin exists
]


def make_cover(job):
    video = ROOT / job["video"]
    if not video.exists():
        raise FileNotFoundError(video)
    cover = COVER_DIR / f"{job['slug']}-cover.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        job["seek"],
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        "scale=1000:1500:force_original_aspect_ratio=decrease,pad=1000:1500:(ow-iw)/2:(oh-ih)/2:black",
        "-q:v",
        "2",
        str(cover),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cover


def post_json(client, url, token, body):
    resp = client.post(url, headers={"Authorization": f"Bearer {token}"}, json=body)
    if resp.status_code >= 400:
        raise RuntimeError(f"POST {url} HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json() if resp.content else {}


def get_json(client, url, token):
    resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code >= 400:
        raise RuntimeError(f"GET {url} HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json() if resp.content else {}


def upload_video(client, api_base, token, video_path):
    reg = post_json(client, f"{api_base}/media", token, {"media_type": "video"})
    media_id = reg.get("media_id") or reg.get("id")
    upload_url = reg.get("upload_url")
    upload_params = reg.get("upload_parameters") or []
    if not media_id or not upload_url:
        raise RuntimeError(f"Unexpected media registration response: {json.dumps(reg)[:500]}")

    if isinstance(upload_params, dict):
        data = upload_params
    else:
        data = {}
        for item in upload_params:
            if isinstance(item, dict):
                key = item.get("name") or item.get("key")
                value = item.get("value")
                if key:
                    data[key] = value

    with open(video_path, "rb") as fh:
        upload = client.post(
            upload_url,
            data=data,
            files={"file": (video_path.name, fh, "video/mp4")},
            timeout=180,
        )
    if upload.status_code not in (200, 201, 204):
        raise RuntimeError(f"video upload HTTP {upload.status_code}: {upload.text[:500]}")

    last = {}
    for _ in range(36):
        time.sleep(5)
        last = get_json(client, f"{api_base}/media/{media_id}", token)
        status = str(last.get("status") or last.get("upload_status") or "").lower()
        if status in ("succeeded", "success", "available", "finished"):
            return media_id
        if status in ("failed", "failure", "error"):
            raise RuntimeError(f"Pinterest media failed: {json.dumps(last)[:500]}")
    raise RuntimeError(f"Pinterest media did not finish: {json.dumps(last)[:500]}")


def create_video_pin(client, api_base, token, board_id, job, media_id, cover_url):
    body = {
        "board_id": board_id,
        "title": job["title"][:100],
        "description": (
            "Seamless mathematical motion art from MathRelaxing. "
            "Explore the full animation pack at mathrelaxing.store."
        ),
        "link": f"{PUBLIC_BASE}/bundle/{job['slug']}?utm_source=pinterest&utm_medium=organic&utm_campaign=pin_repair_video",
        "media_source": {
            "source_type": "video_id",
            "cover_image_url": cover_url,
            "media_id": media_id,
        },
    }
    return post_json(client, f"{api_base}/pins", token, body)


def delete_pin(client, api_base, token, pin_id):
    resp = client.delete(f"{api_base}/pins/{pin_id}", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code in (200, 202, 204, 404):
        return True
    raise RuntimeError(f"DELETE pin {pin_id} HTTP {resp.status_code}: {resp.text[:500]}")


def save_db_record(job, board_id, pin_id, cover_url):
    db = SessionLocal()
    try:
        db.add(
            PinterestPin(
                product_slug=job["slug"],
                product_type="digital",
                variant_idx=90,
                board_id=board_id,
                pin_id=pin_id,
                image_url=cover_url,
                title=job["title"],
                description="Repaired video pin with clear cover and MP4 media.",
                link_url=f"{PUBLIC_BASE}/bundle/{job['slug']}?utm_source=pinterest&utm_medium=organic&utm_campaign=pin_repair_video",
                status="active",
                created_at=datetime.utcnow(),
            )
        )
        for old_id in job.get("delete", []) + DELETE_ONLY:
            old = db.query(PinterestPin).filter(PinterestPin.pin_id == old_id).first()
            if old:
                old.status = "deleted"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def main():
    token = await pin_api._access_token()
    api_base = pin_api._api_base()
    report = json.loads((ROOT / "pinterest_pin_audit_report.json").read_text(encoding="utf-8"))
    boards = {b["name"]: b["id"] for b in report["boards"] if b.get("name") and b.get("id")}
    board_id = boards.get("Mathematical Art Prints")
    if not board_id:
        raise RuntimeError("Mathematical Art Prints board not found")

    created = []
    deleted = []
    with httpx.Client(timeout=60) as client:
        for job in REPLACEMENTS:
            cover = make_cover(job)
            cover_url = f"{PUBLIC_BASE}/static/covers/pinterest-repairs/{cover.name}"
            video_path = ROOT / job["video"]
            print("UPLOAD", job["slug"], video_path.name)
            media_id = upload_video(client, api_base, token, video_path)
            pin = create_video_pin(client, api_base, token, board_id, job, media_id, cover_url)
            pin_id = pin.get("id")
            if not pin_id:
                raise RuntimeError(f"Created pin missing id: {json.dumps(pin)[:500]}")
            created.append({"slug": job["slug"], "pin_id": pin_id, "title": job["title"]})
            save_db_record(job, board_id, pin_id, cover_url)
            for old_id in job["delete"]:
                print("DELETE old", old_id)
                delete_pin(client, api_base, token, old_id)
                deleted.append(old_id)

        for old_id in DELETE_ONLY:
            print("DELETE old-only", old_id)
            delete_pin(client, api_base, token, old_id)
            deleted.append(old_id)

    out = {
        "created": created,
        "deleted": deleted,
        "created_count": len(created),
        "deleted_count": len(deleted),
    }
    (ROOT / "pinterest_pin_repair_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
