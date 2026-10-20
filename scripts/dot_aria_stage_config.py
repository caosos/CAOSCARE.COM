#!/usr/bin/env python3
"""Render private activation candidates; never modify running configuration."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def stage(directory, backend_env, package, owner, profile):
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Staging directory must be private and owner-owned")
    if not re.fullmatch(r"user_[A-Za-z0-9_]+", owner) or not re.fullmatch(r"res_[A-Za-z0-9_]+", profile):
        raise ValueError("Invalid server identity binding")
    token = (directory / "channel.token").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise ValueError("Invalid channel credential")
    env = backend_env.read_text()
    config = (directory / "ha-configuration.before.yaml").read_text()
    ha_secrets = (directory / "ha-secrets.before.yaml").read_text()
    if re.search(r"^\s*(?:export\s+)?CAOSCARE_DOT_ARIA_", env, re.M):
        raise ValueError("Existing channel configuration needs review; refusing replacement")
    if re.search(r"^homeassistant\s*:", config, re.M):
        raise ValueError("Existing homeassistant configuration needs a reviewed merge")
    if re.search(r"^caoscare_dot_aria_authorization\s*:", ha_secrets, re.M):
        raise ValueError("Existing HA channel secret needs review; refusing replacement")
    values = {
        "CAOSCARE_DOT_ARIA_TOKEN_SHA256": hashlib.sha256(token.encode()).hexdigest(),
        "CAOSCARE_DOT_ARIA_OWNER_USER_ID": owner,
        "CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID": profile,
        "CAOSCARE_DOT_ARIA_ALLOWED_HOSTS": "192.168.122.137",
    }
    outputs = {
        "backend.before.env": env,
        "backend.candidate.env": env.rstrip() + "\n\n# Owner-approved Room 214 HA channel\n"
            + "".join(f"{key}={value}\n" for key, value in values.items()),
        "ha-configuration.candidate.yaml": config.rstrip()
            + "\n\nhomeassistant:\n  packages:\n    caoscare_dot_aria: !include caoscare_dot_aria_package.yaml\n",
        "ha-secrets.candidate.yaml": ha_secrets.rstrip()
            + f'\ncaoscare_dot_aria_authorization: "Bearer {token}"\n',
        "caoscare_dot_aria_package.yaml": package.read_text(),
    }
    if any((directory / name).exists() for name in outputs):
        raise ValueError("Activation candidates already exist; refusing overwrite")
    for name, data in outputs.items():
        write_new(directory / name, data)
    return len(outputs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--backend-env", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()
    count = stage(args.directory, args.backend_env, args.package, args.owner, args.profile)
    print(f"PRIVATE_CANDIDATES={count}")
    print("LIVE_CONFIG_CHANGED=no")
