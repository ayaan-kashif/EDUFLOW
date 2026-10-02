"""Small, inspectable calibration of local signals from teacher corrections.

Train and validation groups are separated by question ID, so labels for the
same question never appear on both sides of the reported validation metric.
"""

import random

from app.mapping.signals import SignalScores, combine


def fit_weights(examples):
    questions = sorted({r["question_id"] for r in examples})
    if len(questions) < 10 or len(examples) < 20:
        raise ValueError(
            "Calibration needs at least 20 corrected mappings across 10 distinct questions"
        )
    random.Random(42).shuffle(questions)
    held_out = set(questions[: max(2, len(questions) // 5)])
    train = [r for r in examples if r["question_id"] not in held_out]
    validation = [r for r in examples if r["question_id"] in held_out]

    def mse(rows, weights):
        return sum(
            (combine(SignalScores(**r["signals"]), weights)[0] - r["target"]) ** 2 for r in rows
        ) / len(rows)

    candidates = [
        {"lexical": i / 20, "terminology": 1 - i / 20, "embedding": 0.5, "llm": 0.5}
        for i in range(21)
    ]
    weights = min(candidates, key=lambda w: (mse(train, w), abs(w["lexical"] - 0.5)))
    baseline = mse(validation, None)
    calibrated = mse(validation, weights)
    return {
        "weights": weights,
        "train_samples": len(train),
        "validation_samples": len(validation),
        "train_questions": len(questions) - len(held_out),
        "validation_questions": len(held_out),
        "baseline_validation_mse": baseline,
        "calibrated_validation_mse": calibrated,
        "accepted": calibrated <= baseline,
        "origin": "machine_inferred",
        "confidence": len(train) / (len(train) + 20),
        "note": "Validation error on corrected mappings; not overall precision or a teacher study.",
    }
