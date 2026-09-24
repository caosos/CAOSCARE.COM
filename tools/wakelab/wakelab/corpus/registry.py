"""Reproducible corpus acquisition and provenance manifests.

`fetch()` downloads each configured source into the cache, verifies a pinned
sha256 when one is set, and records url / license / version / retrieval time
/ sha256 / size in <cache>/manifest.json. The manifest (not the data) is what
another engineer needs to reproduce a run; data files are never committed.
"""
import datetime
import hashlib
import json
import os
import urllib.request

from ..config import LAB_DIR, cache_dir, sources

USER_AGENT = "CAOSCare-WakePhraseLab/1 (research; contact via repo)"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_path():
    return os.path.join(cache_dir(), "manifest.json")


def load_manifest():
    try:
        with open(manifest_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def local_path(source_id, spec=None):
    spec = spec or sources()[source_id]
    if spec["kind"] == "local_file":
        path = os.environ.get(spec["path_env"]) or os.path.join(LAB_DIR, spec["default_path"])
        return path if os.path.exists(path) else None
    if spec["kind"] == "file":
        return os.path.join(cache_dir(), source_id + "__" + os.path.basename(spec["url"]))
    return None


def fetch(only=None, include_optional=False, force=False, log=print):
    """Download file sources; returns the updated manifest."""
    manifest = load_manifest()
    for sid, spec in sources().items():
        if only and sid not in only:
            continue
        if spec.get("optional") and not include_optional and not (only and sid in only):
            continue
        entry = {k: spec.get(k) for k in ("kind", "url", "version", "license", "attribution", "use")}
        if spec["kind"] == "file":
            path = local_path(sid, spec)
            if force or not os.path.exists(path):
                log(f"fetch {sid} <- {spec['url']}")
                req = urllib.request.Request(spec["url"], headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=120) as resp, open(path + ".part", "wb") as out:
                    while chunk := resp.read(1 << 20):
                        out.write(chunk)
                os.replace(path + ".part", path)
                entry["retrieved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            else:
                entry["retrieved_at"] = manifest.get(sid, {}).get("retrieved_at")
            digest = _sha256(path)
            if spec.get("sha256") and spec["sha256"] != digest:
                raise RuntimeError(f"{sid}: sha256 mismatch (pinned {spec['sha256']}, got {digest})")
            entry.update(sha256=digest, bytes=os.path.getsize(path), cache_file=os.path.basename(path))
        elif spec["kind"] == "python_package":
            from importlib.metadata import version
            entry["installed_version"] = version(spec["package"])
            if entry["installed_version"] != spec["version"]:
                log(f"WARNING {sid}: installed {entry['installed_version']} != pinned {spec['version']}")
        elif spec["kind"] == "local_file":
            # Private data: record only presence, never the path contents or names.
            entry = {"kind": "local_file", "license": spec["license"],
                     "present": local_path(sid, spec) is not None}
        manifest[sid] = entry
    with open(manifest_path(), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    return manifest
