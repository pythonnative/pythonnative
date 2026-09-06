"""Exercise the actual release-selection shell step and its job outputs."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="Release selection runs on Ubuntu")


@pytest.fixture
def release_repo(tmp_path: Path) -> Path:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-b", "main")
    git("config", "user.name", "Release test")
    git("config", "user.email", "release-test@example.invalid")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", "/dev/null")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.40.0"\n')
    git("add", "pyproject.toml")
    git("commit", "-m", "chore(release): v0.40.0")
    git("tag", "v0.40.0")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("commit", "--allow-empty", "-m", "build(workflows): repair publishing")

    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "python").symlink_to(sys.executable)
    # Keep the test local: replace only external tools, retaining real Git and
    # the exact shell step from release.yml. PSR always appends its outputs,
    # including the existing tag when it reports released=false.
    stubs = {
        "uv": "#!/bin/sh\nexit 0\n",
        "gh": "#!/bin/sh\necho false\n",
        "semantic-release": f"#!{sys.executable}\n"
        + """import os
from pathlib import Path
import subprocess
new_release = os.environ['TEST_RELEASE_MODE'] == 'new'
version = '0.40.1' if new_release else '0.40.0'
if new_release:
    Path('pyproject.toml').write_text('[project]\\nversion = "0.40.1"\\n')
    subprocess.run(['git', 'commit', '-am', 'chore(release): v0.40.1'], check=True)
    subprocess.run(['git', 'tag', 'v0.40.1'], check=True)
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write(f'released={str(new_release).lower()}\\nversion={version}\\ntag=v{version}\\n')
""",
    }
    for name, content in stubs.items():
        path = commands / name
        path.write_text(content)
        path.chmod(0o755)
    return tmp_path


def run_selection(repo: Path, mode: str, recovery_tag: str = "") -> tuple[dict[str, str], dict[str, str]]:
    workflow: dict[str, Any] = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
    )
    job = workflow["jobs"]["release"]
    step = next(step for step in job["steps"] if step.get("id") == "select")
    output_file = repo / "outputs"
    output_file.touch()
    env = {
        **os.environ,
        "PATH": str(repo / "commands") + os.pathsep + os.environ["PATH"],
        "GITHUB_OUTPUT": str(output_file),
        "RUNNER_TEMP": str(repo),
        "RECOVERY_TAG": recovery_tag,
        "TEST_RELEASE_MODE": mode,
    }
    subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]], cwd=repo, env=env, check=True)
    step_outputs = dict(line.split("=", 1) for line in output_file.read_text().splitlines())
    job_outputs = {}
    for name, expression in job["outputs"].items():
        match = re.fullmatch(r"\$\{\{ steps\.select\.outputs\.(\w+) \}\}", expression)
        assert match is not None
        job_outputs[name] = step_outputs.get(match[1], "")
    return step_outputs, job_outputs


def test_no_release_does_not_forward_semantic_release_tag(release_repo: Path) -> None:
    step_outputs, job_outputs = run_selection(release_repo, "none")
    assert step_outputs["released"] == "false"
    assert step_outputs["tag"] == "v0.40.0"
    assert job_outputs == {"tag": "", "commit": ""}


def test_new_release_selects_the_new_tagged_commit(release_repo: Path) -> None:
    _, job_outputs = run_selection(release_repo, "new")
    commit = subprocess.check_output(["git", "rev-parse", "v0.40.1^{commit}"], cwd=release_repo, text=True).strip()
    assert job_outputs == {"tag": "v0.40.1", "commit": commit}


def test_recovery_selects_existing_source_instead_of_main(release_repo: Path) -> None:
    _, job_outputs = run_selection(release_repo, "none", "v0.40.0")
    commit = subprocess.check_output(["git", "rev-parse", "v0.40.0^{commit}"], cwd=release_repo, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=release_repo, text=True).strip()
    assert commit != head
    assert job_outputs == {"tag": "v0.40.0", "commit": commit}
