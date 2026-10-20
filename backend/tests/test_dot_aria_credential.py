"""Credential provisioning uses private files and never rotates implicitly."""
import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2] / "scripts" / "dot_aria_credential.py"
spec = importlib.util.spec_from_file_location("dot_aria_credential", path)
credential = importlib.util.module_from_spec(spec)
spec.loader.exec_module(credential)


def test_private_creation_and_repeat_reuses_same_secret(tmp_path):
    directory = tmp_path / "credential"
    first = credential.provision(directory)
    second = credential.provision(directory)
    assert first["created"] is True and second["created"] is False
    assert first["sha256"] == second["sha256"]
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "channel.token").stat().st_mode & 0o777 == 0o600
    assert "token" not in first


def test_refuses_nonprivate_directory_and_symlink(tmp_path):
    directory = tmp_path / "public"
    directory.mkdir(mode=0o755)
    with pytest.raises(ValueError):
        credential.provision(directory)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError):
        credential.provision(link)


def test_refuses_invalid_existing_secret_without_replacing_it(tmp_path):
    directory = tmp_path / "credential"
    credential.provision(directory)
    path = directory / "channel.token"
    path.write_text("invalid\n")
    with pytest.raises(ValueError):
        credential.provision(directory)
    assert path.read_text() == "invalid\n"


def test_staging_preserves_existing_config_and_never_writes_live_file(tmp_path):
    stage_path = path.parent / "dot_aria_stage_config.py"
    stage_spec = importlib.util.spec_from_file_location("dot_aria_stage_config", stage_path)
    staging = importlib.util.module_from_spec(stage_spec)
    stage_spec.loader.exec_module(staging)
    directory = tmp_path / "private"
    credential.provision(directory)
    env = tmp_path / "backend.env"
    env.write_text("EXISTING_TEST_SETTING=unchanged\n")
    package = tmp_path / "package.yaml"
    package.write_text("script: {}\n")
    (directory / "ha-configuration.before.yaml").write_text("default_config:\nscript: !include scripts.yaml\n")
    (directory / "ha-secrets.before.yaml").write_text("existing_test_secret: fixture\n")
    count = staging.stage(directory, env, package, "user_fixture", "res_fixture")
    assert count == 5
    assert env.read_text() == "EXISTING_TEST_SETTING=unchanged\n"
    candidate = (directory / "backend.candidate.env").read_text()
    assert "CAOSCARE_DOT_ARIA_ALLOWED_HOSTS=192.168.122.137" in candidate
    assert "CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID=res_fixture" in candidate
    assert (directory / "channel.token").read_text().strip() not in candidate
    secret_candidate = directory / "ha-secrets.candidate.yaml"
    assert secret_candidate.stat().st_mode & 0o777 == 0o600
    assert secret_candidate.read_text().startswith("existing_test_secret: fixture\n")
    with pytest.raises(ValueError):
        staging.stage(directory, env, package, "user_fixture", "res_fixture")
