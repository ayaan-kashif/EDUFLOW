import pytest

from app.mapping.calibration import fit_weights


def test_calibration_separates_questions_and_learns_reliable_signal():
    examples = [
        {
            "question_id": str(i),
            "target": target,
            "signals": {"lexical": 0.5, "terminology": target},
        }
        for i in range(10)
        for target in [0, 1]
    ]
    report = fit_weights(examples)
    assert report["weights"]["terminology"] == 1
    assert report["validation_questions"] == 2
    assert report["calibrated_validation_mse"] < report["baseline_validation_mse"]
    assert report["accepted"]


def test_calibration_rejects_too_few_independent_questions():
    with pytest.raises(ValueError):
        fit_weights([{"question_id": "same", "target": 1, "signals": {"lexical": 1}}] * 100)
