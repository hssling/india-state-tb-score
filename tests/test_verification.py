"""Unit tests of the verification checks, on temporary git repositories."""
import subprocess

import pytest

from verification import check_deviations, check_plan_order

PLAN = "# Plan\n\nBefore.\n\n## 13. Deviations\n\nDeviations are logged here.\n"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)


def commit(repo, files, msg):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        git(repo, "add", rel)
    git(repo, "commit", "-m", msg)
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    return tmp_path


def test_clean_history_passes_and_section13_edit_is_allowed(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"src/a.py": "x = 1\n"}, "code")
    commit(repo, {"docs/analysis_plan.md": PLAN + "\n**17 November 2026.**\n\n1. Logged.\n"},
           "deviation")
    assert check_plan_order.problems(repo, reg) == []


def test_edit_before_section13_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    commit(repo, {"docs/analysis_plan.md": PLAN.replace("Before.", "Changed.")}, "edit")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "before section 13" in bad[0]


def test_code_committed_before_registration_is_flagged(repo):
    commit(repo, {"src/a.py": "x = 1\n"}, "code first")
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "not a descendant" in bad[0]


def test_registration_commit_itself_touching_outputs_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN, "outputs/q.csv": "a\n"}, "plan+out")
    assert len(check_plan_order.problems(repo, reg)) == 1


def test_registration_not_ancestor_is_flagged(repo):
    reg = commit(repo, {"docs/analysis_plan.md": PLAN}, "plan")
    git(repo, "checkout", "-q", "--orphan", "other")
    commit(repo, {"docs/analysis_plan.md": PLAN}, "unrelated history")
    bad = check_plan_order.problems(repo, reg)
    assert len(bad) == 1 and "not an ancestor" in bad[0]


PLAN13 = PLAN + "\n**17 November 2026.**\n\n1. A label for q9.csv is exploratory.\n"


def _plan_and_outputs(root, plan, outputs):
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "analysis_plan.md").write_text(plan, encoding="utf-8")
    (root / "outputs").mkdir(exist_ok=True)
    for name, text in outputs.items():
        (root / "outputs" / name).write_text(text, encoding="utf-8")


def test_deviations_passes_without_exploratory(tmp_path):
    _plan_and_outputs(tmp_path, PLAN, {"q9.csv": "a,b\n1,2\n"})
    assert check_deviations.problems(tmp_path) == ([], [])


def test_deviations_flags_unlogged_label_any_case(tmp_path):
    _plan_and_outputs(tmp_path, PLAN, {"q9.csv": "a,b\n1,Exploratory\n"})
    bad, ok = check_deviations.problems(tmp_path)
    assert len(bad) == 1 and "q9.csv" in bad[0] and ok == []


def test_deviations_accepts_logged_label(tmp_path):
    _plan_and_outputs(tmp_path, PLAN13, {"q9.csv": "a,b\n1,exploratory\n"})
    assert check_deviations.problems(tmp_path) == ([], ["outputs/q9.csv (exploratory)"])


def test_deviations_entry_must_name_the_file(tmp_path):
    _plan_and_outputs(tmp_path, PLAN13, {"other.csv": "exploratory\n"})
    assert len(check_deviations.problems(tmp_path)[0]) == 1


def test_plan_order_skips_without_git(tmp_path, capsys):
    """A release archive has no .git: the history check is skipped, not failed."""
    _plan_and_outputs(tmp_path, PLAN, {})
    assert check_plan_order.main(tmp_path) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("SKIPPED: not a git checkout")


def test_check_all_detects_a_git_checkout(tmp_path):
    from verification import check_all
    assert not check_all.is_git_checkout(tmp_path)
    (tmp_path / ".git").mkdir()
    assert check_all.is_git_checkout(tmp_path)
