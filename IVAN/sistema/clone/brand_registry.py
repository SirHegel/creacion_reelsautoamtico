"""Frozen official brand assets. Local reads only; no network during production.

``catalog()`` exposes identity, provenance and permission states without blobs.
``resolve_entities(script)`` recognizes brands; it never selects a motion family.
``assets_for_engine(context='private_review')`` enables the authorized private
mockup. This does not authorize social/commercial publication. The default
``editorial_reel`` remains strict. Add an official source and an explicit
context decision to brand_assets.json to extend the registry; do not silently
substitute text, an unofficial icon, or an approximation for a missing mark.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sistema/clone/brand_assets.json"


class BrandAssetError(ValueError):
    """An asset, checksum, or context cannot be trusted."""


def _load() -> dict[str, Any]:
    if ROOT.name != "IVAN":
        raise BrandAssetError("The registry must remain inside IVAN")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("assets"), dict):
        raise BrandAssetError("Unsupported brand registry schema")
    return data


def _asset_bytes(entry: dict[str, Any]) -> bytes:
    path = (ROOT / entry["path"]).resolve()
    if not path.is_relative_to(ROOT / "recursos/brands"):
        raise BrandAssetError("Brand asset path escaped recursos/brands")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
        raise BrandAssetError(f"Brand asset checksum changed: {entry['id']}")
    mime = entry.get("mime")
    if mime == "image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BrandAssetError("Invalid PNG signature")
    if mime == "image/svg+xml":
        if b"<svg" not in raw or re.search(
            rb"<script\b|<foreignObject\b|\bon\w+\s*=|(?:href|src)\s*=\s*[\"'](?:https?:|//)",
            raw, re.I,
        ):
            raise BrandAssetError("SVG contains active/external content")
    elif mime != "image/png":
        raise BrandAssetError("Only original SVG and PNG brand files are supported")
    return raw


def _context_entry(entry: dict[str, Any], context: str) -> dict[str, Any]:
    decision = entry.get("contexts", {}).get(context)
    if not isinstance(decision, dict):
        return {"usable": False, "reason": "No verified decision for this context"}
    if entry.get("status") != "authentic_verified":
        return {"usable": False, "reason": "Official source/visual verification pending"}
    if context == "private_review":
        allowed = bool(decision.get("user_authorized_preparation"))
    else:
        allowed = bool(decision.get("publication_authorized"))
    return {**decision, "usable": allowed}


def catalog(context: str = "editorial_reel") -> list[dict[str, Any]]:
    """Compact entries, including unavailable assets and their concrete reason."""
    data = _load()
    if context not in data["known_contexts"]:
        raise BrandAssetError(f"Unknown brand use context: {context}")
    result = []
    for asset_id, entry in data["assets"].items():
        decision = _context_entry(entry, context)
        verified = False
        error = None
        try:
            _asset_bytes(entry)
            verified = True
        except (OSError, BrandAssetError) as exc:
            error = str(exc)
        result.append({
            "id": asset_id, "brand": entry["brand"], "label": entry["label"],
            "aliases": entry["aliases"], "kind": "brand_logo",
            "status": entry["status"], "file_verified": verified,
            "usable_in_context": bool(verified and decision["usable"]),
            "context": context, "permission_status": entry["permission_status"],
            "pending_permission": entry["pending_permission"],
            "publication_authorized": bool(decision.get("publication_authorized", False)),
            "reason": error or decision.get("reason", "Context verification pending"),
            "source_page": entry["source_page"], "source_url": entry["source_page"],
            "conditions_url": entry["conditions_url"],
            "allowed_contexts": [k for k in data["known_contexts"] if _context_entry(entry, k)["usable"]],
            "constraints": entry["constraints"],
        })
    return result


def resolve_entities(script: str) -> list[dict[str, Any]]:
    """Identify known brand mentions, not semantic actions or scene families."""
    if not isinstance(script, str):
        raise TypeError("Pass the narration/script text, not a scene-selection rule")
    brands: dict[str, dict[str, Any]] = {}
    for asset_id, entry in _load()["assets"].items():
        group = brands.setdefault(entry["brand"], {
            "brand": entry["brand"], "label": entry["entity_label"],
            "asset_ids": [], "aliases": set(),
        })
        group["asset_ids"].append(asset_id)
        group["aliases"].update(entry["aliases"])
    result = []
    for brand, group in brands.items():
        aliases = sorted(group.pop("aliases"), key=len, reverse=True)
        pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(x) for x in aliases) + r")(?!\w)", re.I)
        matches = [{"start": m.start(), "end": m.end(), "text": m.group(0)} for m in pattern.finditer(script)]
        if matches:
            result.append({**group, "matches": matches})
    return sorted(result, key=lambda x: x["matches"][0]["start"])


def assets_for_engine(
    entities: Any = None, data_uri: bool = False, context: str = "editorial_reel",
) -> dict[str, dict[str, Any]]:
    """Engine asset map, with hash checks and an explicit use-context decision.

    entities may be brand IDs, asset IDs, resolve_entities() entries, or a script.
    data_uri=True adds ``data`` in the existing CLONE runtime's data-URI format.
    No rejected/pending public permission is silently promoted by this function.
    """
    data = _load()
    if context not in data["known_contexts"]:
        raise BrandAssetError(f"Unknown brand use context: {context}")
    wanted: set[str] | None = None
    if entities is not None:
        wanted = set()
        if isinstance(entities, str):
            entities = [entities] if entities in data["assets"] else resolve_entities(entities)
        for item in entities:
            if isinstance(item, str):
                wanted.add(item.casefold())
            elif isinstance(item, dict):
                wanted.update(str(item.get(k, "")).casefold() for k in ["brand", "id"])
                wanted.update(str(x).casefold() for x in item.get("asset_ids", []))
            else:
                raise TypeError("entities must contain brand IDs, asset IDs or entity records")
    result = {}
    for asset_id, entry in data["assets"].items():
        if wanted is not None and not ({asset_id.casefold(), entry["brand"].casefold(), *[x.casefold() for x in entry["aliases"]]} & wanted):
            continue
        decision = _context_entry(entry, context)
        if not decision["usable"]:
            continue
        raw = _asset_bytes(entry)
        result[asset_id] = {
            "path": entry["path"], "width": entry["width"], "height": entry["height"],
            "sha256": entry["sha256"], "mime": entry["mime"], "brand": entry["brand"],
            "aliases": entry["aliases"], "source_url": entry["source_page"],
            "download_url": entry["download_url"], "conditions_url": entry["conditions_url"],
            "kind": "brand_logo", "context": context,
            "verification": "authentic_verified_checksum_verified",
            "publication_authorized": bool(decision.get("publication_authorized", False)),
            "permission_status": entry["permission_status"],
            "pending_permission": entry["pending_permission"],
            "constraints": entry["constraints"], "has_alpha": entry["has_alpha"],
            "private_preparation_only": context == "private_review",
        }
        if "alpha_bbox" in entry:
            result[asset_id]["alpha_bbox"] = entry["alpha_bbox"]
        if data_uri:
            result[asset_id]["data"] = f"data:{entry['mime']};base64," + base64.b64encode(raw).decode("ascii")
    return result


def verify() -> dict[str, Any]:
    """Verify all frozen files without creating files or fetching any network URL."""
    data = _load()
    checked = []
    for asset_id, entry in data["assets"].items():
        _asset_bytes(entry)
        checked.append(asset_id)
    return {"ok": True, "assets_checked": checked, "network_used": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["catalog", "resolve", "verify"])
    parser.add_argument("script", nargs="?", default="")
    parser.add_argument("--context", default="editorial_reel")
    args = parser.parse_args()
    value = verify() if args.command == "verify" else resolve_entities(args.script) if args.command == "resolve" else catalog(args.context)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
