#!/usr/bin/env python3
"""
server.py — Py-ART NEXRAD Level 2 server
Fetches the latest scan for any CONUS NEXRAD site from the public
AWS S3 bucket (noaa-nexrad-level2), renders dual-pol fields as
transparent geo-referenced PNGs, and returns them with lat/lon bounds
so MapLibre can overlay them as an image source.

Usage:
    pip install -r requirements.txt
    python3 server.py
"""

import io
import base64
import logging
import warnings
from datetime import datetime, timedelta, timezone
from threading import Lock

import numpy as np
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import s3fs
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import pyart
import cmweather   # registers NWS colormaps
from flask import Flask, request, jsonify
from flask_cors import CORS

warnings.filterwarnings("ignore")

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nexrad")

app = Flask(__name__)
CORS(app)

# ── AWS clients — boto3 (primary) + s3fs (fallback) ───────────────────────────
S3_BUCKET  = "noaa-nexrad-level2"
S3_REGION  = "us-east-1"

_BOTO_CLIENT = None
_BOTO_LOCK   = Lock()

def get_boto():
    global _BOTO_CLIENT
    with _BOTO_LOCK:
        if _BOTO_CLIENT is None:
            _BOTO_CLIENT = boto3.client(
                "s3",
                region_name=S3_REGION,
                config=Config(signature_version=UNSIGNED),
            )
    return _BOTO_CLIENT

_S3FS       = None
_S3FS_LOCK  = Lock()

def get_s3fs():
    global _S3FS
    with _S3FS_LOCK:
        if _S3FS is None:
            _S3FS = s3fs.S3FileSystem(
                anon=True,
                client_kwargs={"region_name": S3_REGION},
            )
    return _S3FS

# ── S3 file listing ────────────────────────────────────────────────────────────
def _list_keys(site: str, dt: datetime) -> list[str]:
    """
    Return S3 *keys* (no bucket prefix) for V06 files at the given site+date.
    e.g.  2026/06/27/KEOX/KEOX20260627_165423_V06
    Tries boto3 first (most reliable), then s3fs.
    """
    prefix = f"{dt.year}/{dt.month:02d}/{dt.day:02d}/{site.upper()}/"

    # ── boto3 ──────────────────────────────────────────────────────────────────
    try:
        paginator = get_boto().get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                k = obj["Key"]
                if "V06" in k and not k.endswith("_MDM"):
                    keys.append(k)
        if keys:
            log.info("S3(boto3) found %d files for %s %s", len(keys), site, dt.date())
            return sorted(keys)
        # Empty is not an error — just no data for that date
        log.info("S3(boto3) 0 files for %s %s", site, dt.date())
        return []
    except Exception as exc:
        log.warning("S3(boto3) list failed for %s%s: %s", S3_BUCKET, prefix, exc)

    # ── s3fs fallback ──────────────────────────────────────────────────────────
    try:
        full_prefix = f"{S3_BUCKET}/{prefix}"
        raw = get_s3fs().ls(full_prefix, detail=False)
        keys = []
        for path in raw:
            # s3fs returns 'bucket/key'; strip bucket name
            k = path[len(S3_BUCKET) + 1:]
            if "V06" in k and not k.endswith("_MDM"):
                keys.append(k)
        if keys:
            log.info("S3(s3fs) found %d files for %s %s", len(keys), site, dt.date())
        return sorted(keys)
    except Exception as exc:
        log.warning("S3(s3fs)  list failed for %s%s: %s", S3_BUCKET, prefix, exc)

    return []


def latest_key(site: str) -> str | None:
    """Return the S3 key of the most recent V06 file for *site*."""
    now = datetime.now(timezone.utc)
    for delta in range(3):
        keys = _list_keys(site, now - timedelta(days=delta))
        if keys:
            return keys[-1]
    log.error("No NEXRAD data found for %s in last 3 days", site)
    return None

# ── NEXRAD file reading (with cache) ──────────────────────────────────────────
_CACHE:      dict[str, object] = {}
_CACHE_LOCK: Lock               = Lock()
_CACHE_MAX                      = 4

def _open_radar(key: str):
    """Download *key* from S3 and parse with Py-ART. Returns radar object."""
    log.info("Downloading  s3://%s/%s", S3_BUCKET, key)

    # Try boto3 streaming into BytesIO
    try:
        buf = io.BytesIO()
        get_boto().download_fileobj(S3_BUCKET, key, buf)
        buf.seek(0)
        radar = pyart.io.read_nexrad_archive(buf)
        radar.init_gate_longitude_latitude()
        log.info("Parsed via boto3 — fields: %s", list(radar.fields.keys()))
        return radar
    except Exception as exc:
        log.warning("boto3 download failed (%s), trying s3fs …", exc)

    # s3fs fallback
    with get_s3fs().open(f"{S3_BUCKET}/{key}", "rb") as fh:
        radar = pyart.io.read_nexrad_archive(fh)
    radar.init_gate_longitude_latitude()
    log.info("Parsed via s3fs — fields: %s", list(radar.fields.keys()))
    return radar


def read_radar(key: str):
    with _CACHE_LOCK:
        if key in _CACHE:
            log.info("Cache hit: %s", key.split("/")[-1])
            return _CACHE[key]

    radar = _open_radar(key)

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            evict = next(iter(_CACHE))
            del _CACHE[evict]
            log.info("Evicted cache: %s", evict.split("/")[-1])
        _CACHE[key] = radar

    return radar

# ── Field config ───────────────────────────────────────────────────────────────
FIELD_CFG = {
    "reflectivity": {
        "pyart_key": "reflectivity",
        "aliases":   ["reflectivity", "REF", "DBZ", "reflectivity_horizontal"],
        "vmin": -20, "vmax": 70,
        "cmap": "NWSRef",
        "label": "BASE REFLECTIVITY",
        "unit": "dBZ",
    },
    "corrected_reflectivity": {
        "pyart_key": "reflectivity",
        "aliases":   ["reflectivity", "REF", "DBZ"],
        "vmin": -20, "vmax": 70,
        "cmap": "NWSRef",
        "label": "REFLECTIVITY X",
        "unit": "dBZ",
    },
    "max_reflectivity": {
        "pyart_key": "reflectivity",
        "aliases":   ["reflectivity", "REF", "DBZ"],
        "vmin": -20, "vmax": 70,
        "cmap": "NWSRef",
        "label": "MAX REFLECTIVITY",
        "unit": "dBZ",
        "all_sweeps": True,
    },
    "velocity": {
        "pyart_key": "velocity",
        "aliases":   ["velocity", "VEL", "mean_doppler_velocity"],
        "vmin": -30, "vmax": 30,
        "cmap": "NWSVel",
        "label": "BASE VELOCITY",
        "unit": "m/s",
    },
    "storm_relative_velocity": {
        "pyart_key": "velocity",
        "aliases":   ["velocity", "VEL", "mean_doppler_velocity"],
        "vmin": -30, "vmax": 30,
        "cmap": "NWSVel",
        "label": "STORM REL. VELOCITY",
        "unit": "m/s",
    },
    "cross_correlation_ratio": {
        "pyart_key": "cross_correlation_ratio",
        "aliases":   ["cross_correlation_ratio", "RHO", "RHOHV", "RHV"],
        "vmin": 0.0, "vmax": 1.05,
        "cmap": "NWS_CC",
        "label": "CORR. COEFFICIENT",
        "unit": "",
    },
    "differential_reflectivity": {
        "pyart_key": "differential_reflectivity",
        "aliases":   ["differential_reflectivity", "ZDR"],
        "vmin": -2.0, "vmax": 6.0,
        "cmap": "HomeyerRainbow",
        "label": "DIFF. REFLECTIVITY",
        "unit": "dB",
    },
    "differential_phase": {
        "pyart_key": "differential_phase",
        "aliases":   ["differential_phase", "PHI", "PHIDP"],
        "vmin": 0, "vmax": 180,
        "cmap": "ChaseSpectral",
        "label": "SPEC. DIFF. PHASE",
        "unit": "deg",
    },
    "spectrum_width": {
        "pyart_key": "spectrum_width",
        "aliases":   ["spectrum_width", "SW", "WIDTH"],
        "vmin": 0.0, "vmax": 10.0,
        "cmap": "NWS_SPW",
        "label": "SPECTRUM WIDTH",
        "unit": "m/s",
    },
}

PRODUCT_TO_FIELD = {
    "N0Q": "reflectivity",
    "N0B": "corrected_reflectivity",
    "NCR": "max_reflectivity",
    "N0U": "velocity",
    "N0S": "storm_relative_velocity",
    "NRO": "velocity",
    "N0C": "cross_correlation_ratio",
    "N0K": "differential_phase",
    "N0X": "differential_reflectivity",
    "NSW": "spectrum_width",
}

# ── Field resolution (NEXRAD field names vary by VCP/mode) ────────────────────
def resolve_field(radar, cfg: dict) -> str | None:
    available = set(radar.fields.keys())
    for name in cfg.get("aliases", [cfg["pyart_key"]]):
        if name in available:
            return name
    return None

# ── PNG renderer ───────────────────────────────────────────────────────────────
_MPL_LOCK = Lock()

def render(radar, field_key: str, sweep_idx: int = 0) -> dict:
    cfg = FIELD_CFG[field_key]
    field = resolve_field(radar, cfg)
    if field is None:
        available = list(radar.fields.keys())
        raise ValueError(
            f"Field '{cfg['pyart_key']}' not available. "
            f"Radar has: {available}"
        )

    sweep_idx = min(sweep_idx, radar.nsweeps - 1)

    if cfg.get("all_sweeps"):
        all_lons, all_lats, all_data = [], [], []
        for s in range(radar.nsweeps):
            sl = radar.get_slice(s)
            all_lons.append(radar.gate_longitude["data"][sl])
            all_lats.append(radar.gate_latitude["data"][sl])
            all_data.append(radar.fields[field]["data"][sl])
        lons  = np.concatenate(all_lons)
        lats  = np.concatenate(all_lats)
        fdata = np.ma.concatenate(all_data)
    else:
        sl    = radar.get_slice(sweep_idx)
        lons  = radar.gate_longitude["data"][sl]
        lats  = radar.gate_latitude["data"][sl]
        fdata = radar.fields[field]["data"][sl]

    fdata = np.ma.masked_invalid(fdata)

    lon_min, lon_max = float(np.nanmin(lons)), float(np.nanmax(lons))
    lat_min, lat_max = float(np.nanmin(lats)), float(np.nanmax(lats))

    lat_c   = (lat_min + lat_max) / 2
    cos_lat = max(np.cos(np.deg2rad(lat_c)), 0.01)
    fig_w   = 8.0
    fig_h   = fig_w * ((lat_max - lat_min) / ((lon_max - lon_min) * cos_lat + 1e-9))

    cmap = plt.get_cmap(cfg["cmap"]).copy()
    cmap.set_bad(alpha=0.0)
    norm = Normalize(vmin=cfg["vmin"], vmax=cfg["vmax"])

    with _MPL_LOCK:
        fig = plt.figure(figsize=(fig_w, fig_h), facecolor="none")
        ax  = fig.add_axes([0, 0, 1, 1], facecolor="none")
        ax.axis("off")
        ax.pcolormesh(lons, lats, fdata, cmap=cmap, norm=norm,
                      shading="auto", linewidth=0, rasterized=True)
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, dpi=150, pad_inches=0)
        plt.close(fig)

    buf.seek(0)

    try:
        t         = pyart.util.datetime_from_radar(radar)
        scan_time = t.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        scan_time = datetime.now(timezone.utc).isoformat()

    return {
        "image":  base64.b64encode(buf.read()).decode(),
        "bounds": {"west": lon_min, "east": lon_max,
                   "south": lat_min, "north": lat_max},
        "time":   scan_time,
        "label":  cfg["label"],
        "unit":   cfg["unit"],
        "field":  field_key,
        "sweep":  int(sweep_idx),
        "nsweeps": int(radar.nsweeps),
        "available_fields": list(radar.fields.keys()),
    }

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/api/radar")
def radar_route():
    site    = request.args.get("site",    "KTLX").upper().strip()
    product = request.args.get("product", "").upper().strip()
    field   = request.args.get("field",   "reflectivity").strip()
    sweep   = int(request.args.get("sweep", "0"))

    if product and product in PRODUCT_TO_FIELD:
        field = PRODUCT_TO_FIELD[product]

    if field not in FIELD_CFG:
        return jsonify({
            "error": f"Unknown field '{field}'",
            "valid_fields":   list(FIELD_CFG.keys()),
            "valid_products": list(PRODUCT_TO_FIELD.keys()),
        }), 400

    key = latest_key(site)
    if key is None:
        return jsonify({
            "error": (
                f"No NEXRAD Level-2 data found for {site} on AWS S3. "
                "Check that the site ID is valid (4 chars, e.g. KTLX) "
                "and that your machine has internet access to s3.amazonaws.com."
            )
        }), 404

    try:
        radar  = read_radar(key)
        result = render(radar, field, sweep)
        result.update(site=site, s3key=key)
        return jsonify(result)
    except Exception as exc:
        log.exception("Render failed for %s / %s", site, field)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/latest")
def latest_route():
    site = request.args.get("site", "KTLX").upper()
    key  = latest_key(site)
    if key is None:
        return jsonify({"error": f"No data found for {site}"}), 404
    fn = key.split("/")[-1]
    try:
        # filename: KXXX_YYYYMMDD_HHMMSS_V06  or  KXXXYYYYMMDD_HHMMSS_V06
        parts = fn.replace("_V06", "").split("_")
        ts    = datetime.strptime(parts[-2] + parts[-1], "%Y%m%d%H%M%S")
        scan_time = ts.replace(tzinfo=timezone.utc).isoformat()
    except Exception:
        scan_time = None
    return jsonify({"site": site, "file": fn, "time": scan_time, "key": key})


@app.route("/api/fields")
def fields_route():
    site = request.args.get("site", "KTLX").upper()
    key  = latest_key(site)
    if key is None:
        return jsonify({"error": f"No data found for {site}"}), 404
    try:
        radar = read_radar(key)
        return jsonify({
            "site":              site,
            "file":              key.split("/")[-1],
            "pyart_fields":      list(radar.fields.keys()),
            "supported_fields":  list(FIELD_CFG.keys()),
            "supported_products": list(PRODUCT_TO_FIELD.keys()),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/health")
def health_route():
    return jsonify({
        "status": "ok",
        "pyart":  pyart.__version__,
        "tip":    "If /api/radar returns 404, visit /api/test-s3 to diagnose S3 access",
    })


@app.route("/api/test-s3")
def test_s3_route():
    """
    Diagnostic endpoint. Visit http://localhost:5000/api/test-s3
    to see exactly why S3 access might be failing.
    """
    site = request.args.get("site", "KTLX").upper()
    now  = datetime.now(timezone.utc)
    results = []

    for delta in range(2):
        dt     = now - timedelta(days=delta)
        prefix_key  = f"{dt.year}/{dt.month:02d}/{dt.day:02d}/{site}/"
        prefix_full = f"{S3_BUCKET}/{prefix_key}"

        # ── boto3 ──────────────────────────────────────────────────────────────
        try:
            resp  = get_boto().list_objects_v2(
                Bucket=S3_BUCKET, Prefix=prefix_key, MaxKeys=5
            )
            files = [o["Key"].split("/")[-1] for o in resp.get("Contents", [])]
            results.append({
                "method": "boto3", "date": str(dt.date()),
                "status": "OK", "files": files,
                "count": resp.get("KeyCount", 0),
            })
            if files:
                break
        except Exception as exc:
            results.append({
                "method": "boto3", "date": str(dt.date()),
                "status": "ERROR", "error": str(exc),
                "hint": (
                    "403 Forbidden usually means the bucket is requester-pays. "
                    "Set up AWS credentials (aws configure) and the server will "
                    "use them automatically via boto3's credential chain."
                ) if "403" in str(exc) else str(exc),
            })

        # ── s3fs ───────────────────────────────────────────────────────────────
        try:
            raw   = get_s3fs().ls(prefix_full, detail=False)
            files = [p.split("/")[-1] for p in raw if "V06" in p]
            results.append({
                "method": "s3fs", "date": str(dt.date()),
                "status": "OK", "files": files[:5], "count": len(files),
            })
            if files:
                break
        except Exception as exc:
            results.append({
                "method": "s3fs", "date": str(dt.date()),
                "status": "ERROR", "error": str(exc),
            })

    any_ok = any(r["status"] == "OK" and r.get("count", 0) > 0 for r in results)
    return jsonify({
        "bucket":   S3_BUCKET,
        "site":     site,
        "tests":    results,
        "verdict":  "S3 accessible — data found" if any_ok else (
            "S3 access FAILED for all methods. "
            "If you see '403 Forbidden', the bucket may now be requester-pays. "
            "Fix: run  aws configure  and enter your AWS access key. "
            "If you see a connection error, check your firewall/proxy."
        ),
    })


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("  ┌────────────────────────────────────────────────────────┐")
    print("  │  Py-ART NEXRAD Server   http://0.0.0.0:5000           │")
    print("  │  Test: http://localhost:5000/api/health                │")
    print("  │  Data: http://localhost:5000/api/radar?site=KTLX      │")
    print("  │  Ctrl-C to stop                                        │")
    print("  └────────────────────────────────────────────────────────┘")
    print()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)