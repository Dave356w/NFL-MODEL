"""Invariants of the signed-commit path.

Every ledger commit this repo has made shows as Unverified: a runner has no
signing key, so `git push` cannot produce anything GitHub can verify. The fix
sends the same content through `createCommitOnBranch`, which GitHub signs.
What is pinned here is the part that can silently go wrong -- which files get
sent, what happens when the branch tip moves, and that a failure still lands
the data rather than losing a forward snapshot.
"""

import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import commit_data


def _status(*entries):
    """Join porcelain -z fields the way git emits them."""
    return "".join(f"{e}\0" for e in entries)


def test_written_files_are_additions_and_missing_ones_deletions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "kept.csv").write_text("a,b\n1,2\n")
    adds, dels = commit_data.changed_paths(
        ["data"],
        status_text=_status(" M data/kept.csv", " D data/gone.csv"),
    )
    assert adds == ["data/kept.csv"]
    assert dels == ["data/gone.csv"]


def test_untracked_files_are_sent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "leans_2026-08-27_xw.csv").write_text("x\n")
    adds, _ = commit_data.changed_paths(
        ["data"], status_text=_status("?? data/leans_2026-08-27_xw.csv")
    )
    assert adds == ["data/leans_2026-08-27_xw.csv"]


def test_rename_becomes_an_addition_and_a_deletion(tmp_path, monkeypatch):
    """A rebuild dump is renamed, not rewritten; both halves must be sent."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "rebuild_leans.csv").write_text("x\n")
    adds, dels = commit_data.changed_paths(
        ["data"],
        # git -z emits the new path in the status field and the old path as a
        # bare following field.
        status_text=_status("R  data/rebuild_leans.csv", "data/leans.csv"),
    )
    assert adds == ["data/rebuild_leans.csv"]
    assert dels == ["data/leans.csv"]


def test_contents_are_base64_of_the_file_on_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    body = "game_pk,lean\n1,HOU\n"
    (tmp_path / "data" / "led.csv").write_text(body)
    changes = commit_data.file_changes(["data/led.csv"], ["data/old.csv"])
    assert changes["deletions"] == [{"path": "data/old.csv"}]
    sent = changes["additions"][0]
    assert sent["path"] == "data/led.csv"
    assert base64.b64decode(sent["contents"]).decode() == body


def test_no_changes_makes_no_api_call(monkeypatch):
    monkeypatch.setattr(commit_data, "changed_paths", lambda paths: ([], []))
    monkeypatch.setattr(commit_data, "graphql", _explode)
    monkeypatch.setattr(commit_data, "git_commit_and_push", _explode)
    assert commit_data.main(["--branch", "main", "--message", "ledger"]) == 0


def _explode(*args, **kwargs):
    raise AssertionError("should not be called")


class _Moves:
    """remote_head() answers with each tip in turn."""

    def __init__(self, *oids):
        self.oids = list(oids)

    def __call__(self, branch):
        return self.oids.pop(0) if len(self.oids) > 1 else self.oids[0]


def test_retries_when_the_branch_moved_without_touching_our_files(monkeypatch):
    monkeypatch.setattr(commit_data, "remote_head", _Moves("aaa", "bbb", "bbb"))
    monkeypatch.setattr(commit_data, "touches_ours", lambda o, n, ours: [])
    monkeypatch.setattr(commit_data.time, "sleep", lambda s: None)
    seen = []

    def fake_graphql(token, query, variables, timeout=60):
        seen.append(variables["input"]["expectedHeadOid"])
        if len(seen) == 1:
            raise RuntimeError("expected head oid mismatch")
        return {"createCommitOnBranch": {"commit": {"oid": "c" * 40, "url": "u"}}}

    monkeypatch.setattr(commit_data, "graphql", fake_graphql)
    commit = commit_data.api_commit(
        "tok", "o/r", "main", "ledger",
        {"additions": [{"path": "data/x.csv", "contents": ""}], "deletions": []},
    )
    assert commit["oid"] == "c" * 40
    assert seen == ["aaa", "bbb"]


def test_refuses_when_the_intervening_commit_wrote_one_of_our_files(monkeypatch):
    """The `git pull --rebase` conflict refusal, kept in the API path."""
    monkeypatch.setattr(commit_data, "remote_head", _Moves("aaa", "bbb", "bbb"))
    monkeypatch.setattr(
        commit_data, "touches_ours", lambda o, n, ours: ["data/led.csv"]
    )
    monkeypatch.setattr(commit_data.time, "sleep", lambda s: None)

    def fake_graphql(token, query, variables, timeout=60):
        raise RuntimeError("expected head oid mismatch")

    monkeypatch.setattr(commit_data, "graphql", fake_graphql)
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        commit_data.api_commit(
            "tok", "o/r", "main", "ledger",
            {"additions": [{"path": "data/led.csv", "contents": ""}],
             "deletions": []},
        )


def test_api_failure_falls_back_to_the_push_that_cannot_lose_a_snapshot(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "led.csv").write_text("x\n")
    monkeypatch.setattr(
        commit_data, "changed_paths", lambda paths: (["data/led.csv"], [])
    )
    monkeypatch.setattr(commit_data, "api_commit", _explode_api)
    pushed = []
    monkeypatch.setattr(
        commit_data, "git_commit_and_push",
        lambda branch, message: pushed.append((branch, message)),
    )
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    assert commit_data.main(["--branch", "main", "--message", "ledger"]) == 0
    assert pushed == [("main", "ledger")]
    assert "::warning::" in capsys.readouterr().out


def _explode_api(*args, **kwargs):
    raise RuntimeError("graphql exploded")


def test_no_fallback_flag_lets_the_failure_surface(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        commit_data, "changed_paths", lambda paths: (["data/led.csv"], [])
    )
    monkeypatch.setattr(commit_data, "file_changes",
                        lambda adds, dels: {"additions": [], "deletions": []})
    monkeypatch.setattr(commit_data, "api_commit", _explode_api)
    monkeypatch.setattr(commit_data, "git_commit_and_push", _explode)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    with pytest.raises(RuntimeError, match="graphql exploded"):
        commit_data.main(
            ["--branch", "main", "--message", "ledger", "--no-fallback"]
        )


def test_first_attempt_is_pinned_to_the_checkout_not_the_tip(monkeypatch):
    """A stale checkout whose newer commits wrote our file must be refused."""
    monkeypatch.setattr(commit_data, "remote_head", _Moves("tip", "tip"))
    checked = []

    def touches(old, new, ours):
        checked.append((old, new))
        return ["data/led.csv"]

    monkeypatch.setattr(commit_data, "touches_ours", touches)
    monkeypatch.setattr(commit_data.time, "sleep", lambda s: None)
    seen = []

    def fake_graphql(token, query, variables, timeout=60):
        seen.append(variables["input"]["expectedHeadOid"])
        raise RuntimeError("expected head oid mismatch")

    monkeypatch.setattr(commit_data, "graphql", fake_graphql)
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        commit_data.api_commit(
            "tok", "o/r", "main", "ledger",
            {"additions": [{"path": "data/led.csv", "contents": ""}],
             "deletions": []}, base="checkout")
    assert seen == ["checkout"]
    assert checked == [("checkout", "tip")]


def test_stale_checkout_that_touched_nothing_of_ours_still_commits(monkeypatch):
    monkeypatch.setattr(commit_data, "remote_head", _Moves("tip", "tip"))
    monkeypatch.setattr(commit_data, "touches_ours", lambda o, n, ours: [])
    monkeypatch.setattr(commit_data.time, "sleep", lambda s: None)
    seen = []

    def fake_graphql(token, query, variables, timeout=60):
        seen.append(variables["input"]["expectedHeadOid"])
        if len(seen) == 1:
            raise RuntimeError("expected head oid mismatch")
        return {"createCommitOnBranch": {"commit": {"oid": "c" * 40, "url": "u"}}}

    monkeypatch.setattr(commit_data, "graphql", fake_graphql)
    out = commit_data.api_commit(
        "tok", "o/r", "main", "ledger",
        {"additions": [{"path": "data/x.csv", "contents": ""}], "deletions": []},
        base="checkout")
    assert out["oid"] == "c" * 40 and seen == ["checkout", "tip"]


def test_main_passes_the_checkout_as_the_base(monkeypatch):
    monkeypatch.setattr(commit_data, "changed_paths", lambda paths: (["data/x.csv"], []))
    monkeypatch.setattr(commit_data, "file_changes",
                        lambda a, d: {"additions": [], "deletions": []})
    monkeypatch.setattr(commit_data, "local_head", lambda: "checkout")
    got = {}

    def fake_api(token, repo, branch, message, changes, attempts=3, base=None):
        got["base"] = base
        return {"oid": "c" * 40, "url": "u"}

    monkeypatch.setattr(commit_data, "api_commit", fake_api)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    commit_data.main(["--branch", "main", "--message", "m", "--no-fallback"])
    assert got["base"] == "checkout"




ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _build_yml():
    with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as fh:
        return fh.read()


def test_the_build_checks_out_the_latest_main():
    build = _build_yml().split("\n  build:\n", 1)[1]
    assert "uses: actions/checkout@v4\n        with:\n          ref: main" in build


def test_data_is_committed_through_the_signed_path_after_validation():
    text = _build_yml()
    assert "python commit_data.py --branch main" in text
    assert "git push origin" not in text and "git commit" not in text
    step = text.split("Commit ledger and snapshots", 1)[1]
    assert step.index("python validate_data_files.py") < step.index("python commit_data.py")
