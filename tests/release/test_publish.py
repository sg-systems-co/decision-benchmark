"""Tests for release/publish.py. Hugging Face is always stubbed; no network calls."""

from __future__ import annotations

import random
import re
import string
from types import SimpleNamespace

import pytest
import requests
from huggingface_hub.errors import HfHubHTTPError

import publish
import stage

TAG = "v0.9.0-alpha.1.1"
NEW = "sgsystems/decision-benchmark-ap-invoices"
OLD = "sgsystems/decision-benchmark-ap-my-sg"


def fake_token() -> str:
    rng = random.Random(11)
    return "hf" + "_" + "".join(rng.choice(string.ascii_letters) for _ in range(34))


@pytest.fixture
def staged(tmp_path):
    out = tmp_path / "hf"
    stage.stage(stage.REPO_ROOT, out)
    # Between releases the repo card describes the next spec version (v0.10 while TAG is a v0.9
    # tag). These tests check the publish mechanics for TAG, so the staged card carries TAG's label.
    card = out / "README.md"
    card.write_text(re.sub(r"\*\*Version v\d+\.\d+ —", "**Version v0.9 —", card.read_text(encoding="utf-8"), count=1),
                    encoding="utf-8")
    return out


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", fake_token())
    monkeypatch.setenv("RELEASE_GIT_SHA", "abc1234")


def http_error(code: int) -> HfHubHTTPError:
    resp = requests.Response()
    resp.status_code = code
    return HfHubHTTPError(f"{code} error", response=resp)


class FakeApi:
    def __init__(self, fail: dict[str, int] | None = None, tags: tuple[str, ...] = (),
                 existing: tuple[str, ...] = ()):
        self.fail = fail or {}
        self.tags = tags
        self.existing = set(existing)
        self.calls: list[str] = []
        self.written: list[str] = []

    def _call(self, name):
        self.calls.append(name)
        if name in self.fail:
            raise http_error(self.fail[name])

    def _write(self, repo_id):
        """Every call that creates or changes a repo goes through here. Old ids are never written."""
        assert repo_id not in publish.OLD_REPO_IDS, f"wrote to old id {repo_id}"
        self.written.append(repo_id)

    def repo_exists(self, repo_id, **kw):
        self._call("repo_exists")
        assert kw == {"repo_type": "dataset"}
        return repo_id in self.existing

    def move_repo(self, from_id, to_id, **kw):
        self._call("move_repo")
        assert (from_id, to_id, kw) == (OLD, NEW, {"repo_type": "dataset"})
        self._write(to_id)
        self.existing.discard(from_id)
        self.existing.add(to_id)

    def whoami(self):
        self._call("whoami")
        return {"name": "sg-bot"}

    def create_repo(self, repo_id, **kw):
        self._call("create_repo")
        self._write(repo_id)
        assert repo_id == publish.REPO_ID and kw == {"repo_type": "dataset", "private": False, "exist_ok": True}

    def create_collection(self, **kw):
        self._call("create_collection")
        assert kw["namespace"] == "sgsystems" and kw["exists_ok"] is True
        return SimpleNamespace(slug="sgsystems/sg-systems-decision-benchmark-0123")

    def add_collection_item(self, slug, **kw):
        self._call("add_collection_item")
        self._write(kw["item_id"])
        assert kw == {"item_id": publish.REPO_ID, "item_type": "dataset", "exists_ok": True}

    def list_repo_refs(self, repo_id, **kw):
        self._call("list_repo_refs")
        return SimpleNamespace(tags=[SimpleNamespace(name=t) for t in self.tags])

    def upload_folder(self, **kw):
        self._call("upload_folder")
        self._write(kw["repo_id"])
        assert kw["delete_patterns"] == "*" and kw["repo_type"] == "dataset"
        assert kw["commit_message"] == f"{TAG} from sg-systems-co/decision-benchmark@abc1234"
        return SimpleNamespace(oid="deadbeef")

    def create_tag(self, repo_id, **kw):
        self._call("create_tag")
        self._write(repo_id)
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
    assert api.calls == ["whoami", "repo_exists", "repo_exists", "create_repo", "create_collection",
                         "add_collection_item", "list_repo_refs", "upload_folder", "create_tag"]
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


def test_repo_id_comes_from_the_task_set_spec():
    from decision_benchmark.core.task_set import get

    assert publish.REPO_ID == get("ap-invoices").hf_repo_id == NEW
    assert publish.MOVED_FROM == {NEW: OLD}


def test_old_repo_is_moved_once_when_the_new_id_does_not_exist(staged, token_env, capsys):
    api = FakeApi(existing=(OLD,))
    code, out = run(staged, capsys, api=api)
    assert code == 0, out
    assert api.calls[:5] == ["whoami", "repo_exists", "repo_exists", "move_repo", "create_repo"]
    assert api.calls.count("move_repo") == 1
    assert f"moved {OLD} -> {NEW}" in out
    assert set(api.written) == {NEW}


def test_no_move_when_the_new_id_exists(staged, token_env, capsys):
    # After a move Hugging Face redirects the old id, so both may look like they exist.
    api = FakeApi(existing=(OLD, NEW))
    code, out = run(staged, capsys, api=api)
    assert code == 0, out
    assert "move_repo" not in api.calls and api.calls.count("repo_exists") == 1
    assert set(api.written) == {NEW}


def test_no_move_when_neither_exists(staged, token_env, capsys):
    api = FakeApi()
    assert run(staged, capsys, api=api)[0] == 0
    assert "move_repo" not in api.calls and set(api.written) == {NEW}


@pytest.mark.parametrize("extra", [[], ["--dry-run"]], ids=["real", "dry_run"])
def test_never_writes_under_the_old_id(staged, token_env, capsys, monkeypatch, extra):
    """Hard rule: if the target were ever an old id, stop before any API call."""
    monkeypatch.setattr(publish, "REPO_ID", OLD)
    api = FakeApi()
    code, out = run(staged, capsys, api=api, extra=extra)
    assert code == 1 and "old repo id" in out
    assert api.calls == []


def test_move_failure_stops_before_any_write(staged, token_env, capsys):
    api = FakeApi(existing=(OLD,), fail={"move_repo": 403})
    code, out = run(staged, capsys, api=api)
    assert code == 1 and "HF_TOKEN lacks the rights to move" in out
    assert api.written == []


def _unlabelled_stage(staged, label):
    card = staged / "README.md"
    card.write_text(re.sub(r"\*\*Version v\d+\.\d+ —", f"**Version {label} —", card.read_text(encoding="utf-8"), count=1),
                    encoding="utf-8")


def test_unreleased_spec_version_is_read_from_the_changelog():
    assert publish.unreleased_spec_version() == "v0.10"


def test_unreleased_card_passes_the_pr_dry_run_only(staged, capsys):
    _unlabelled_stage(staged, "v0.10")
    code, out = run(staged, capsys, extra=["--dry-run"])
    assert code == 1 and "no version label for v0.9" in out
    code, out = run(staged, capsys, extra=["--dry-run", "--allow-unreleased-card"])
    assert code == 0 and "dry run, nothing uploaded" in out


def test_unreleased_card_flag_needs_dry_run(staged, token_env, capsys):
    with pytest.raises(SystemExit):
        run(staged, capsys, api=FakeApi(), extra=["--allow-unreleased-card"])


def test_any_other_card_label_still_fails(staged, capsys):
    _unlabelled_stage(staged, "v0.11")
    code, out = run(staged, capsys, extra=["--dry-run", "--allow-unreleased-card"])
    assert code == 1 and "no version label for v0.9 or v0.10" in out
