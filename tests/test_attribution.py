import subprocess

import pytest

from scripts.prepare_attribution_cleanup import TARGET_LINES, clean_message, prepare


def test_exact_attribution_only():
    meaningful = (
        b"Add Claude integration\n\nHuman author\nCo-Authored-By: Human <human@example.org>\n"
    )
    original = meaningful + b"\n".join(TARGET_LINES) + b"\n"
    assert clean_message(original) == meaningful
    assert (
        clean_message(b"Meaningful reference: Generated with Claude Code support\n")
        == b"Meaningful reference: Generated with Claude Code support\n"
    )


def test_cleanup_preserves_trees_humans_tags_and_merge_topology(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args], stderr=subprocess.DEVNULL)

    git("init")
    git("config", "user.name", "Human Maintainer")
    git("config", "user.email", "human@example.org")
    git("config", "commit.gpgsign", "false")
    (source / "code.py").write_text("print('preserve me')\n")
    git("add", "code.py")
    git("commit", "-m", "Human feature\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    git("tag", "-a", "v1", "-m", "Human release")
    root = git("rev-parse", "HEAD").decode().strip()
    git("checkout", "-b", "other")
    git("commit", "--allow-empty", "-m", "Branch commit")
    other = git("rev-parse", "HEAD").decode().strip()
    git("checkout", "-b", "mainline", root)
    git("commit", "--allow-empty", "-m", "Main commit")
    git("merge", "--no-ff", other, "-m", "Meaningful merge")
    before = git("rev-parse", "HEAD")
    report = prepare(source, tmp_path / "prepared")
    assert report["published"] is False
    assert report["verified_commits"] == 4
    assert report["changed_commits"] == 4
    assert len(report["targeted_commits"]) == 1
    assert report["changed_tag_objects"]
    assert git("rev-parse", "HEAD") == before
    with pytest.raises(ValueError):
        prepare(source, source / "bad")
