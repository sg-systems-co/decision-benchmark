#!/usr/bin/env python3
"""Publish the staged folder (build/hf/) to Hugging Face as one tagged release.

  publish.py --tag v0.9.0-alpha.1 --dry-run   checks only, no network calls
  publish.py --tag v0.9.0-alpha.1             uploads (needs HF_TOKEN in the environment)
  publish.py --print-changelog-tag            prints the newest tag in CHANGELOG.md

Real runs do the Hugging Face setup themselves:
  1. check the token (whoami)
  2. create the dataset repo if missing (exist_ok)
  3. create the collection if missing and add the dataset to it
  4. refuse to run if the tag already exists on Hugging Face
  5. upload build/hf/ to main in one commit, removing files not in this release
  6. tag that commit with the release tag

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
HF_NAMESPACE = "sgsystems"
REPO_ID = f"{HF_NAMESPACE}/decision-benchmark-ap-my-sg"
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


def verify_release(tag: str, staged: Path, root: Path = REPO_ROOT) -> list[str]:
    """Offline checks. Returns the staged file list. Raises ReleaseError."""
    m = TAG_RE.match(tag)
    if not m:
        raise ReleaseError(f"tag {tag!r} is not of the form vX.Y.Z or vX.Y.Z-suffix")
    spec_version = f"v{m.group(1)}.{m.group(2)}"
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## \[{re.escape(tag)}\]", changelog, re.MULTILINE):
        raise ReleaseError(f"CHANGELOG.md has no entry '## [{tag}]'")
    if not staged.is_dir():
        raise ReleaseError(f"staged folder {staged} does not exist (run release/stage.py first)")
    card = (staged / "README.md").read_text(encoding="utf-8") if (staged / "README.md").exists() else ""
    if f"**Version {spec_version} —" not in card:
        raise ReleaseError(f"dataset card has no version label for {spec_version}")
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


def publish(tag: str, staged: Path, api_factory: Callable = _default_api_factory) -> None:
    """Real upload. Raises ReleaseError with a message that is safe to print."""
    from huggingface_hub.errors import HfHubHTTPError

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
    args = parser.parse_args(argv)
    try:
        if args.print_changelog_tag:
            print(newest_changelog_tag())
            return 0
        if not args.tag:
            parser.error("--tag is required")
        files = verify_release(args.tag, args.staged.resolve())
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
