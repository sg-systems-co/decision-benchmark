"""Tests for release/publish.py. Hugging Face is always stubbed; no network calls."""

from __future__ import annotations

import random
import string
from types import SimpleNamespace

import pytest
import requests
from huggingface_hub.errors import HfHubHTTPError

import publish
import stage

TAG = "v0.9.0-alpha.1"


def fake_token() -> str:
    rng = random.Random(11)
    return "hf" + "_" + "".join(rng.choice(string.ascii_letters) for _ in range(34))


@pytest.fixture
def staged(tmp_path):
    out = tmp_path / "hf"
    stage.stage(stage.REPO_ROOT, out)
    return out


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", fake_token())
    monkeypatch.setenv("GITHUB_SHA", "abc1234")


def http_error(code: int) -> HfHubHTTPError:
    resp = requests.Response()
    resp.status_code = code
    return HfHubHTTPError(f"{code} error", response=resp)


class FakeApi:
    def __init__(self, fail: dict[str, int] | None = None, tags: tuple[str, ...] = ()):
        self.fail = fail or {}
        self.tags = tags
        self.calls: list[str] = []

    def _call(self, name):
        self.calls.append(name)
        if name in self.fail:
            raise http_error(self.fail[name])

    def whoami(self):
        self._call("whoami")
        return {"name": "sg-bot"}

    def create_repo(self, repo_id, **kw):
        self._call("create_repo")
        assert repo_id == publish.REPO_ID and kw == {"repo_type": "dataset", "private": False, "exist_ok": True}

    def create_collection(self, **kw):
        self._call("create_collection")
        assert kw["namespace"] == "sgsystems" and kw["exists_ok"] is True
        return SimpleNamespace(slug="sgsystems/sg-systems-decision-benchmark-0123")

    def add_collection_item(self, slug, **kw):
        self._call("add_collection_item")
        assert kw == {"item_id": publish.REPO_ID, "item_type": "dataset", "exists_ok": True}

    def list_repo_refs(self, repo_id, **kw):
        self._call("list_repo_refs")
        return SimpleNamespace(tags=[SimpleNamespace(name=t) for t in self.tags])

    def upload_folder(self, **kw):
        self._call("upload_folder")
        assert kw["delete_patterns"] == "*" and kw["repo_type"] == "dataset"
        assert kw["commit_message"] == f"{TAG} from sg-systems-co/decision-benchmark@abc1234"
        return SimpleNamespace(oid="deadbeef")

    def create_tag(self, repo_id, **kw):
        self._call("create_tag")
        assert kw["tag"] == TAG and kw["revision"] == "deadbeef"


def run(staged, capsys, api=None, extra=()):
    def factory():
        if api is None:
            raise AssertionError("the dry run must not create an API client")
        return api

    code = publish.main(["--tag", TAG, "--staged", str(staged), *extra], api_factory=factory)
    out = capsys.readouterr()
    return code, out.out + out.err


def test_dry_run_makes_no_api_calls(staged, token_env, capsys):
    code, out = run(staged, capsys, api=None, extra=["--dry-run"])
    assert code == 0
    assert "dry run, nothing uploaded" in out
    assert "schema/output.schema.json" in out
    assert fake_token() not in out


def test_real_run_calls_in_order_and_never_prints_token(staged, token_env, capsys):
    api = FakeApi()
    code, out = run(staged, capsys, api=api)
    assert code == 0, out
    assert api.calls == ["whoami", "create_repo", "create_collection", "add_collection_item",
                         "list_repo_refs", "upload_folder", "create_tag"]
    assert fake_token() not in out


@pytest.mark.parametrize("step", ["create_repo", "create_collection", "add_collection_item", "upload_folder"])
def test_403_gives_clear_rights_message(staged, token_env, capsys, step):
    api = FakeApi(fail={step: 403})
    code, out = run(staged, capsys, api=api)
    assert code == 1
    assert "HF_TOKEN lacks the rights to" in out
    assert "write access to the 'sgsystems' organisation" in out
    assert fake_token() not in out


def test_401_on_whoami_says_token_rejected(staged, token_env, capsys):
    code, out = run(staged, capsys, api=FakeApi(fail={"whoami": 401}))
    assert code == 1 and "HF_TOKEN was rejected" in out and fake_token() not in out


def test_no_upload_when_403_happens_before_upload(staged, token_env, capsys):
    api = FakeApi(fail={"create_collection": 403})
    run(staged, capsys, api=api)
    assert "upload_folder" not in api.calls


def test_existing_tag_is_never_overwritten(staged, token_env, capsys):
    api = FakeApi(tags=(TAG,))
    code, out = run(staged, capsys, api=api)
    assert code == 1 and "already exists" in out
    assert "upload_folder" not in api.calls


def test_missing_token_fails(staged, monkeypatch, capsys):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    code, out = run(staged, capsys, api=FakeApi())
    assert code == 1 and "HF_TOKEN is not set" in out


@pytest.mark.parametrize("tag", ["0.9.0", "v0.9", "v0.9.0;rm -rf", "release"])
def test_bad_tag_format_fails(staged, capsys, tag):
    assert publish.main(["--tag", tag, "--staged", str(staged), "--dry-run"]) == 1


def test_tag_without_changelog_entry_fails(staged, capsys):
    assert publish.main(["--tag", "v0.9.7", "--staged", str(staged), "--dry-run"]) == 1
    assert "no entry" in capsys.readouterr().err


def test_tag_for_other_spec_version_fails(staged, capsys):
    assert publish.main(["--tag", "v1.0.0", "--staged", str(staged), "--dry-run"]) == 1


def test_print_changelog_tag(capsys):
    assert publish.main(["--print-changelog-tag"]) == 0
    assert capsys.readouterr().out.strip() == TAG
