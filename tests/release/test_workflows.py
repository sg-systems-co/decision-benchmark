"""Structure of the two workflows: where secrets may appear and what triggers publishing."""

from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[2] / ".github/workflows"


def load(name):
    data = yaml.safe_load((WF / name).read_text())
    # PyYAML reads the bare key `on` as True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def test_guards_use_no_secrets():
    assert "${{ secrets." not in (WF / "guards.yml").read_text()


def test_publish_triggers():
    wf = load("hf-publish.yml")
    assert set(wf["on"]) == {"pull_request", "workflow_dispatch"}  # no push trigger
    tag = wf["on"]["workflow_dispatch"]["inputs"]["tag"]
    assert tag["required"] is True and tag["type"] == "string"
    assert wf["permissions"] == {"contents": "read"}


def test_dry_run_job_has_no_secrets_and_publish_only_on_dispatch():
    wf = load("hf-publish.yml")
    jobs = wf["jobs"]
    assert jobs["dry-run"]["if"] == "github.event_name == 'pull_request'"
    assert jobs["publish"]["if"] == "github.event_name == 'workflow_dispatch'"
    assert "${{ secrets." not in yaml.safe_dump(jobs["dry-run"])


def test_token_only_in_the_upload_step():
    steps = load("hf-publish.yml")["jobs"]["publish"]["steps"]
    with_secret = [s["name"] for s in steps if "${{ secrets." in yaml.safe_dump(s)]
    assert with_secret == ["Upload to Hugging Face and tag the revision"]
    upload = steps[-1]
    assert upload["env"]["HF_TOKEN"] == "${{ secrets.HF_TOKEN }}"
    assert "HF_TOKEN" not in upload["run"]  # never on a command line or echoed


def test_inputs_never_interpolated_into_shell():
    # ${{ inputs.tag }} may only appear in env: or with:, never inside run: scripts.
    for job in load("hf-publish.yml")["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), step.get("name")


def test_actions_pinned_by_sha():
    for name in ("guards.yml", "hf-publish.yml"):
        for line in (WF / name).read_text().splitlines():
            if "uses:" in line:
                ref = line.split("uses:")[1].split("#")[0].strip()
                assert len(ref.split("@")[1]) == 40, line
