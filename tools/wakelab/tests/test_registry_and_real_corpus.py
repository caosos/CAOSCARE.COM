import hashlib
import os

import pytest

from wakelab.corpus import registry


def test_fetch_records_provenance_and_verifies_pin(tmp_path, monkeypatch):
    src = tmp_path / "words.txt"
    src.write_text("area EH1 R IY0 AH0\n")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    spec = {"kind": "file", "url": src.as_uri(), "version": "t", "license": "test",
            "attribution": "test", "use": "test", "sha256": digest}
    monkeypatch.setenv("WAKELAB_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(registry, "sources", lambda: {"demo": spec})
    m = registry.fetch(log=lambda *_: None)
    assert m["demo"]["sha256"] == digest and m["demo"]["license"] == "test"
    spec["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="sha256 mismatch"):
        registry.fetch(log=lambda *_: None)


def test_local_facility_source_records_presence_only(tmp_path, monkeypatch):
    names = tmp_path / "names.txt"
    names.write_text("Private Person\n")
    spec = {"kind": "local_file", "path_env": "WAKELAB_FACILITY_NAMES", "default_path": "x",
            "license": "private"}
    monkeypatch.setenv("WAKELAB_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("WAKELAB_FACILITY_NAMES", str(names))
    monkeypatch.setattr(registry, "sources", lambda: {"facility_local": spec})
    m = registry.fetch(log=lambda *_: None)
    assert m["facility_local"] == {"kind": "local_file", "license": "private", "present": True}


REAL = os.path.join(os.environ.get("WAKELAB_CACHE") or os.path.expanduser("~/.cache/caoscare-wakelab"),
                    "corpus_v1.pkl.gz")


@pytest.mark.skipif(not os.path.exists(REAL), reason="real corpus not built (python -m wakelab build)")
def test_real_corpus_aria_and_controls(cfg):
    from wakelab.inspect import Lab
    from wakelab.report import render
    lab = Lab(cfg, corpus_path=REAL)
    r = lab.inspect("aria")
    text = render(r)
    assert r["verdict"] == "REJECT"
    assert '"area"' in text and "IDENTICAL phonemes" in text
    assert '"common area"' in text and ('"that area"' in text or '"the area"' in text)
    # Calibration controls: a production wake phrase passes the text stage;
    # an ordinary common word does not.
    assert lab.inspect("okay nabu")["verdict"] == "PASS (text stage)"
    assert lab.inspect("hello")["verdict"] == "REJECT"
