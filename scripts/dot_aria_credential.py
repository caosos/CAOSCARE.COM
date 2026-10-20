#!/usr/bin/env python3
"""Provision an owner-approved local channel secret without displaying it.

No network, application settings, accounts, or service state are changed.
Existing credentials are reused only if regular, private, owned, and valid.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat


def provision(directory: Path) -> dict:
    directory.mkdir(mode=0o700, parents=False, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Credential directory must be owner-only and not a symlink")
    path = directory / "channel.token"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        created = False
    else:
        created = True
        with os.fdopen(fd, "w") as handle:
            handle.write(secrets.token_hex(32) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Credential file must be regular, owner-only, and owned")
        token = handle.read(128).strip()
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise ValueError("Existing credential format is invalid; refusing replacement")
    return {"created": created, "path": str(path), "mode": "0600",
            "sha256": hashlib.sha256(token.encode()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = provision(args.directory)
    print(f"CREDENTIAL_CREATED={str(result['created']).lower()}")
    print(f"CREDENTIAL_PATH={result['path']}")
    print(f"CREDENTIAL_MODE={result['mode']}")
    print("ACTIVATED=no")
