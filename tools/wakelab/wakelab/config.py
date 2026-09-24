"""Paths and YAML configuration for the Wake Phrase Lab.

The lab is research tooling only: nothing in production (room-node/,
backend/, frontend/) imports it, and it never touches a running listener.
"""
import os

import yaml

LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(LAB_DIR, "config")
DOMAIN_DIR = os.path.join(LAB_DIR, "wakelab", "corpus", "domain")
RUNS_DIR = os.path.join(LAB_DIR, "runs")


def cache_dir():
    path = os.environ.get("WAKELAB_CACHE") or os.path.expanduser("~/.cache/caoscare-wakelab")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def load_yaml(name):
    with open(os.path.join(CONFIG_DIR, name), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def settings(path=None):
    if path:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    return load_yaml("default.yaml")


def sources():
    return load_yaml("sources.yaml")["sources"]
