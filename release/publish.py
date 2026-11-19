#!/usr/bin/env python3
"""Publish the staged folder (build/hf/) to Hugging Face as one tagged release.

  publish.py --tag v0.9.0-alpha.1 --dry-run   checks only, no network calls
  publish.py --tag v0.9.0-alpha.1             uploads (needs HF_TOKEN in the environment)
  publish.py --print-changelog-tag            prints the newest tag in CHANGELOG.md
  publish.py --tag T --dry-run --allow-unreleased-card
                                              pull-request dry run between releases: the card
                                              may also carry the spec version that CHANGELOG's
                                              [Unreleased] section names ("Spec: vX.Y ...")

Real runs do the Hugging Face setup themselves:
  1. check the token (whoami)
  2. if the task set's old repo id exists and the new one doesn't, move (rename) the old
     repo to the new id, once; Hugging Face then redirects the old URL
     create the dataset repo if missing (exist_ok)
  3. create the collection if missing and add the dataset to it
  4. refuse to run if the tag already exists on Hugging Face
  5. upload build/hf/ to main in one commit, removing files not in this release
  6. tag that commit with the release tag

The repo id comes from the task set's spec (TaskSetSpec.hf_repo_id). Nothing is
ever created, uploaded or tagged under an old id in MOVED_FROM (hard rule).

The token is read from the HF_TOKEN environment variable by huggingface_hub.
It is never printed, logged or passed on a command line.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_public  # noqa: E402
import stage  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TASK_SET = "ap-invoices"
HF_NAMESPACE = "sgsystems"


def spec_repo_id(task_set: str = TASK_SET) -> str:
    import decision_benchmark.task_sets  # noqa: F401  (registers every task set)
    from decision_benchmark.core.task_set import get

    return get(task_set).hf_repo_id


REPO_ID = spec_repo_id()
MOVED_FROM = {"sgsystems/decision-benchmark-ap-invoices": "sgsystems/decision-benchmark-ap-my-sg"}
"""New repo id -> the old id it was renamed from. Old ids are read-only for this script."""
OLD_REPO_IDS = frozenset(MOVED_FROM.values())
REPO_TYPE = "dataset"
COLLECTION_TITLE = "SG Systems Decision Benchmark"
COLLECTION_DESCRIPTION = "Open benchmarks for business decisions in Southeast Asia."
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z][0-9A-Za-z.-]*))?$")

RIGHTS_HELP = (
    "HF_TOKEN needs write access to the '{ns}' organisation on Hugging Face: it must be able to "
    "create and write dataset repos and to create and edit collections. Replace the HF_TOKEN repo "
    "secret with a token that has the write role in '{ns}' (or a fine-grained token with those "
    "permissions), then start the workflow again."
).format(ns=HF_NAMESPACE)


class ReleaseError(Exception):
    pass


def newest_changelog_tag(root: Path = REPO_ROOT) -> str:
    m = re.search(r"^## \[(v[^\]]+)\]", (root / "CHANGELOG.md").read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        raise ReleaseError("CHANGELOG.md has no release entry")
    return m.group(1)


def unreleased_spec_version(root: Path = REPO_ROOT) -> str | None:
    """The spec version named by CHANGELOG's [Unreleased] section ("Spec: vX.Y ..."), if any."""
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## \[Unreleased\]\s*\n(.*?)(?=^## \[)", changelog, re.MULTILINE | re.DOTALL)
    spec = re.search(r"^Spec: (v\d+\.\d+)\b", m.group(1), re.MULTILINE) if m else None
    return spec.group(1) if spec else None


PIN_RE = re.compile(r"^Engine: (\S+)\. Rules as of: (\d{4}-\d{2}-\d{2})\.", re.MULTILINE)
PINNED_FROM = (0, 10)
"""Release entries from spec v0.10 on pin the engine and the rules' as-of date (A12 plan §9)."""


def check_engine_pin(tag: str, changelog: str, spec: tuple[int, int]) -> None:
    """From v0.10, the tag's CHANGELOG entry states "Engine: <version>. Rules as of: <date>." and the engine version is
    the package being published (the version recorded in every answer key)."""
    if spec < PINNED_FROM:
        return
    from decision_benchmark import __version__

    entry = re.search(rf"^## \[{re.escape(tag)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL)
    pin = PIN_RE.search(entry.group(1)) if entry else None
    if pin is None:
        raise ReleaseError(f"CHANGELOG entry '## [{tag}]' has no line 'Engine: <version>. Rules as of: <date>.'")
    if pin.group(1) != __version__:
        raise ReleaseError(f"CHANGELOG entry pins engine {pin.group(1)}, the package is {__version__}")


def verify_release(tag: str, staged: Path, root: Path = REPO_ROOT, allow_unreleased_card: bool = False) -> list[str]:
    """Offline checks. Returns the staged file list. Raises ReleaseError.

    allow_unreleased_card (pull-request dry runs only): between releases the card in the repo
    describes the next spec version, so its label may also be the [Unreleased] spec version.
    Every other check stays the same. A real publish never sets it."""
    m = TAG_RE.match(tag)
    if not m:
        raise ReleaseError(f"tag {tag!r} is not of the form vX.Y.Z or vX.Y.Z-suffix")
    spec_version = f"v{m.group(1)}.{m.group(2)}"
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## \[{re.escape(tag)}\]", changelog, re.MULTILINE):
        raise ReleaseError(f"CHANGELOG.md has no entry '## [{tag}]'")
    check_engine_pin(tag, changelog, (int(m.group(1)), int(m.group(2))))
    if not staged.is_dir():
        raise ReleaseError(f"staged folder {staged} does not exist (run release/stage.py first)")
    card = (staged / "README.md").read_text(encoding="utf-8") if (staged / "README.md").exists() else ""
    labels = [spec_version]
    if allow_unreleased_card and (nxt := unreleased_spec_version(root)) and nxt != spec_version:
        labels.append(nxt)
    if not any(f"**Version {v} —" in card for v in labels):
        raise ReleaseError(f"dataset card has no version label for {' or '.join(labels)}")
    if not (staged / "docs" / f"spec-{spec_version}.md").exists():
        raise ReleaseError(f"staged folder has no docs/spec-{spec_version}.md")
    findings = check_public.check(staged, "staged")
    if findings:
        raise ReleaseError("check_public failed:\n" + "\n".join(map(str, findings)))
    return sorted(check_public.list_files(staged, "staged"))


def git_sha(root: Path = REPO_ROOT) -> str:
    """The commit being published: the checked-out tag, not GITHUB_SHA (which is the
    default branch on workflow_dispatch). RELEASE_GIT_SHA overrides, for tests."""
    if os.environ.get("RELEASE_GIT_SHA"):
        return os.environ["RELEASE_GIT_SHA"]
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _default_api_factory():
    from huggingface_hub import HfApi

    return HfApi()  # reads HF_TOKEN from the environment


def check_target(repo_id: str) -> None:
    """Hard rule: never create, upload to or tag a repo under an old (moved) id."""
    if repo_id in OLD_REPO_IDS:
        raise ReleaseError(f"{repo_id} is an old repo id; nothing may be created or written under it.")


def publish(tag: str, staged: Path, api_factory: Callable = _default_api_factory) -> None:
    """Real upload. Raises ReleaseError with a message that is safe to print."""
    from huggingface_hub.errors import HfHubHTTPError

    check_target(REPO_ID)
    if not os.environ.get("HF_TOKEN"):
        raise ReleaseError("HF_TOKEN is not set. Add it as a repo secret named HF_TOKEN.")
    api = api_factory()
    commit_message = f"{tag} from sg-systems-co/decision-benchmark@{git_sha()}"

    def step(name: str, what: str, fn):
        print(f"publish: {name}")
        try:
            return fn()
        except HfHubHTTPError as exc:
            code = _status(exc)
            if code == 401:
                raise ReleaseError(f"HF_TOKEN was rejected while trying to {what} (HTTP 401: invalid, expired "
                                   f"or revoked). {RIGHTS_HELP}") from None
            if code == 403:
                raise ReleaseError(f"HF_TOKEN lacks the rights to {what} (HTTP 403). {RIGHTS_HELP}") from None
            raise ReleaseError(f"Hugging Face call failed while trying to {what} (HTTP {code}).") from None

    user = step("checking the token", "identify the token owner", api.whoami)
    print(f"publish: token belongs to {user.get('name', '?') if isinstance(user, dict) else '?'}")
    old = MOVED_FROM.get(REPO_ID)
    if old is not None:
        new_exists = step("checking the new repo id", f"check whether {REPO_ID} exists",
                          lambda: api.repo_exists(REPO_ID, repo_type=REPO_TYPE))
        old_exists = not new_exists and step("checking the old repo id", f"check whether {old} exists",
                                             lambda: api.repo_exists(old, repo_type=REPO_TYPE))
        if old_exists:
            step("moving the old repo to the new id", f"move {old} to {REPO_ID}",
                 lambda: api.move_repo(from_id=old, to_id=REPO_ID, repo_type=REPO_TYPE))
            print(f"publish: moved {old} -> {REPO_ID}; the old URL now redirects")
    step("creating the dataset repo if missing", f"create the dataset repo {REPO_ID}",
         lambda: api.create_repo(REPO_ID, repo_type=REPO_TYPE, private=False, exist_ok=True))
    collection = step(
        "creating the collection if missing", f"create the collection '{COLLECTION_TITLE}' in {HF_NAMESPACE}",
        lambda: api.create_collection(title=COLLECTION_TITLE, namespace=HF_NAMESPACE,
                                      description=COLLECTION_DESCRIPTION, private=False, exists_ok=True))
    step("adding the dataset to the collection", f"add {REPO_ID} to the collection",
         lambda: api.add_collection_item(collection.slug, item_id=REPO_ID, item_type=REPO_TYPE, exists_ok=True))
    refs = step("checking existing tags", f"read the tags of {REPO_ID}",
                lambda: api.list_repo_refs(REPO_ID, repo_type=REPO_TYPE))
    if tag in {t.name for t in refs.tags}:
        raise ReleaseError(f"tag {tag} already exists on {REPO_ID}. Releases are never overwritten; "
                           "make a new tag.")
    info = step("uploading", f"upload files to {REPO_ID}",
                lambda: api.upload_folder(folder_path=str(staged), repo_id=REPO_ID, repo_type=REPO_TYPE,
                                          commit_message=commit_message, delete_patterns="*"))
    step("tagging", f"create tag {tag} on {REPO_ID}",
         lambda: api.create_tag(REPO_ID, tag=tag, revision=info.oid, repo_type=REPO_TYPE,
                                tag_message=commit_message))
    print(f"publish: done. https://huggingface.co/datasets/{REPO_ID}/tree/{tag}")


def main(argv: list[str] | None = None, api_factory: Callable = _default_api_factory) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag")
    parser.add_argument("--staged", type=Path, default=stage.DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true", help="run all offline checks, make no network calls")
    parser.add_argument("--print-changelog-tag", action="store_true")
    parser.add_argument("--allow-unreleased-card", action="store_true",
                        help="dry runs only: the card may carry CHANGELOG's [Unreleased] spec version")
    args = parser.parse_args(argv)
    try:
        if args.print_changelog_tag:
            print(newest_changelog_tag())
            return 0
        if not args.tag:
            parser.error("--tag is required")
        if args.allow_unreleased_card and not args.dry_run:
            parser.error("--allow-unreleased-card only works with --dry-run")
        check_target(REPO_ID)
        files = verify_release(args.tag, args.staged.resolve(), allow_unreleased_card=args.allow_unreleased_card)
        print(f"publish: release {args.tag} -> https://huggingface.co/datasets/{REPO_ID}")
        print(f"publish: collection '{COLLECTION_TITLE}' in {HF_NAMESPACE}")
        print(f"publish: {len(files)} files:")
        for line in stage.manifest_lines(args.staged.resolve(), files):
            print(f"  {line}")
        if args.dry_run:
            print("publish: dry run, nothing uploaded")
            return 0
        publish(args.tag, args.staged.resolve(), api_factory)
        return 0
    except ReleaseError as exc:
        print(f"publish: ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
