"""The Mistake Detective benchmark as a regression test (see docs/EVALUATION.md).

Hard guarantees: correct work is never flagged, no misconception is misattributed or invented,
'unknown' is never turned into a confident verdict, nothing raises. Recall must not regress.
"""
import pytest

from tools.evaluate_detective import load, run, score

RECALL_FLOOR = 0.97          # measured 0.983 (115/117) when the benchmark was introduced


@pytest.fixture(scope="module")
def results():
    rows = run(load())
    return score(rows)


def test_no_false_positives_on_correct_work(results):
    m, problems = results
    assert m["negatives"] >= 100
    assert m["FP"] == 0, problems["false positives (correct work flagged)"]


def test_no_misattributed_or_invented_diagnoses(results):
    m, problems = results
    assert m["misattributed"] == 0, problems["misattributions (wrong misconception named)"]
    assert m["invented"] == 0, problems["invented diagnosis (must not name a rule)"]


def test_unknown_is_never_overclaimed(results):
    m, problems = results
    assert m["unknown_overclaim"] == 0, problems["overclaimed (expected 'unknown')"]


def test_no_exceptions(results):
    _, problems = results
    assert not problems.get("errors"), problems.get("errors")


def test_recall_and_rule_naming_do_not_regress(results):
    m, _ = results
    assert m["recall"] >= RECALL_FLOOR
    assert m["rule_correct"] == m["with_expected_rule"]


def test_latency_budget(results):
    m, _ = results
    assert m["max_s"] < 10, "a single step must stay far below the 25 s UI timeout"
