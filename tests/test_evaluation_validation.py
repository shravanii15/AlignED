"""
test_evaluation_validation.py

The extraction benchmark must fail closed: it may only compute and write
metrics when predictions cover exactly the gold-set items. Before, a
missing-ids check only printed a warning and the run went on to save a
legitimate-looking evaluation_results.json (an empty LLM file scored F1 = 0).
"""

import json
import os
import runpy

import pytest

from evaluate_extraction import PredictionValidationError, validate_predictions

GOLD_IDS = ["C001", "C002", "P001"]


def pred(item_id, *terms):
    return {"id": item_id, "predicted_skills": [{"term": t, "type": "technology"} for t in terms]}


def test_complete_predictions_pass():
    validate_predictions("LLM", GOLD_IDS, [pred("C001", "Python"), pred("C002"), pred("P001", "SQL")])


def test_missing_ids_are_rejected_and_named():
    with pytest.raises(PredictionValidationError, match="missing 2 gold-set id"):
        validate_predictions("LLM", GOLD_IDS, [pred("C001", "Python")])


def test_completely_empty_predictions_are_rejected():
    with pytest.raises(PredictionValidationError):
        validate_predictions("LLM", GOLD_IDS, [])


def test_duplicate_ids_are_rejected():
    with pytest.raises(PredictionValidationError, match="duplicate ids"):
        validate_predictions("LLM", GOLD_IDS, [pred("C001"), pred("C001"), pred("C002"), pred("P001")])


def test_unknown_ids_are_rejected():
    with pytest.raises(PredictionValidationError, match="not in the gold set"):
        validate_predictions("LLM", GOLD_IDS, [pred("C001"), pred("C002"), pred("P001"), pred("X999")])


@pytest.mark.parametrize("bad_entry", [
    "not a dict",
    {"predicted_skills": []},
    {"id": "C001"},
    {"id": "C001", "predicted_skills": "Python"},
    {"id": "C001", "predicted_skills": [{"type": "technology"}]},
    {"id": "C001", "predicted_skills": [{"term": 5}]},
])
def test_malformed_entries_are_rejected(bad_entry):
    with pytest.raises(PredictionValidationError):
        validate_predictions("LLM", GOLD_IDS, [bad_entry, pred("C002"), pred("P001")])


def test_non_list_input_is_rejected():
    with pytest.raises(PredictionValidationError):
        validate_predictions("LLM", GOLD_IDS, {"C001": []})


def test_main_does_not_write_results_when_validation_fails(tmp_path, monkeypatch):
    """End to end: an incomplete LLM file must raise and leave
    evaluation_results.json unwritten."""
    import evaluate_extraction as ev

    gold = [{"id": "C001", "essential_skills_or_knowledge": [{"name": "Python"}], "essential_technologies": [], "optional": []}]
    paths = {name: str(tmp_path / f"{name}.json") for name in ("gold", "baseline", "llm", "results")}
    json.dump(gold, open(paths["gold"], "w"))
    json.dump([pred("C001", "Python")], open(paths["baseline"], "w"))
    json.dump([], open(paths["llm"], "w"))  # LLM run produced nothing

    monkeypatch.setattr(ev, "GOLD_LABELS_PATH", paths["gold"])
    monkeypatch.setattr(ev, "BASELINE_PREDICTIONS_PATH", paths["baseline"])
    monkeypatch.setattr(ev, "LLM_PREDICTIONS_PATH", paths["llm"])
    monkeypatch.setattr(ev, "RESULTS_PATH", paths["results"])

    with pytest.raises(PredictionValidationError):
        ev.main()
    assert not os.path.exists(paths["results"])


def test_main_writes_results_for_a_complete_run(tmp_path, monkeypatch):
    import evaluate_extraction as ev

    gold = [{"id": "C001", "essential_skills_or_knowledge": [{"name": "Python"}], "essential_technologies": [], "optional": []}]
    paths = {name: str(tmp_path / f"{name}.json") for name in ("gold", "baseline", "llm", "results")}
    json.dump(gold, open(paths["gold"], "w"))
    json.dump([pred("C001", "Python")], open(paths["baseline"], "w"))
    json.dump([pred("C001", "Python")], open(paths["llm"], "w"))
    monkeypatch.setattr(ev, "GOLD_LABELS_PATH", paths["gold"])
    monkeypatch.setattr(ev, "BASELINE_PREDICTIONS_PATH", paths["baseline"])
    monkeypatch.setattr(ev, "LLM_PREDICTIONS_PATH", paths["llm"])
    monkeypatch.setattr(ev, "RESULTS_PATH", paths["results"])

    ev.main()
    results = json.load(open(paths["results"]))
    assert results["llm"]["f1"] == 1.0 and results["num_gold_items"] == 1
