"""System Usability Scale (SUS) scoring script for usability evaluation.

The SUS is a 10-item questionnaire with a 5-point Likert scale (1=Strongly Disagree,
5=Strongly Agree). Items 1,3,5,7,9 are positive; items 2,4,6,8,10 are negative.

Scoring:
    - For odd items (positive): score = response - 1
    - For even items (negative): score = 5 - response
    - Sum all adjusted scores, multiply by 2.5 -> range 0-100
    - SUS >= 68 is considered above average

Prerequisites:
    None (uses only standard library)

Usage:
    cd backend
    venv/bin/python scripts/eval/sus_scoring.py --responses sus_responses.json

    Where sus_responses.json is a list of participant response arrays:
    [
      [4, 2, 4, 1, 5, 2, 4, 1, 5, 2],  # participant 1
      [3, 3, 4, 2, 4, 2, 3, 1, 4, 3],  # participant 2
      ...
    ]

    Each array has 10 values (1-5) corresponding to the 10 SUS items.

Output:
    Prints per-participant scores and aggregate statistics.
    Saves a JSON report to eval_reports/sus_<timestamp>.json

Targets (from evaluation plan):
    - SUS >= 68 (above average)
    - Minimum n = 15 participants
"""
import argparse
import json
import math
from datetime import datetime
from pathlib import Path

SUS_ITEMS = [
    "I think that I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to be able to use this system.",
    "I found the various functions in this system were well integrated.",
    "I thought there was too much inconsistency in this system.",
    "I would imagine that most people would learn to use this system very quickly.",
    "I found the system very cumbersome to use.",
    "I felt very confident using the system.",
    "I needed to learn a lot of things before I could get going with this system.",
]

POSITIVE_ITEMS = {1, 3, 5, 7, 9}  # 1-indexed
NEGATIVE_ITEMS = {2, 4, 6, 8, 10}


def score_participant(responses: list[int]) -> dict:
    """Score a single participant's SUS responses."""
    if len(responses) != 10:
        raise ValueError(f"Expected 10 responses, got {len(responses)}")

    adjusted: list[int] = []
    for i, raw in enumerate(responses, start=1):
        if not 1 <= raw <= 5:
            raise ValueError(f"Response {i} = {raw} is out of range (1-5)")
        if i in POSITIVE_ITEMS:
            adjusted.append(raw - 1)
        else:
            adjusted.append(5 - raw)

    total = sum(adjusted)
    sus_score = total * 2.5  # range 0-100

    return {
        "responses": responses,
        "adjusted_scores": adjusted,
        "total": total,
        "sus_score": round(sus_score, 1),
    }


def compute_statistics(scores: list[float]) -> dict:
    """Compute aggregate statistics for a list of SUS scores."""
    n = len(scores)
    if n == 0:
        return {"n": 0}
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n if n > 0 else 0
    std_dev = math.sqrt(variance)
    sorted_scores = sorted(scores)
    median = sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
    return {
        "n": n,
        "mean": round(mean, 1),
        "std_dev": round(std_dev, 1),
        "median": round(median, 1),
        "min": round(min(scores), 1),
        "max": round(max(scores), 1),
        "above_average": mean >= 68,
    }


def main():
    parser = argparse.ArgumentParser(description="Score SUS questionnaire responses.")
    parser.add_argument("--responses", required=True, help="Path to JSON file with participant response arrays")
    args = parser.parse_args()

    with open(args.responses) as f:
        all_responses = json.load(f)

    if not isinstance(all_responses, list):
        print("Error: responses file must be a JSON array of response arrays")
        sys.exit(1)

    print(f"SUS Scoring — {len(all_responses)} participant(s)\n")
    print("SUS Questionnaire Items:")
    for i, item in enumerate(SUS_ITEMS, 1):
        polarity = "+" if i in POSITIVE_ITEMS else "-"
        print(f"  {i:2d}. [{polarity}] {item}")
    print()

    results = []
    sus_scores = []

    for idx, responses in enumerate(all_responses, start=1):
        try:
            result = score_participant(responses)
            results.append(result)
            sus_scores.append(result["sus_score"])
            print(f"  Participant {idx}: SUS score = {result['sus_score']}")
        except ValueError as e:
            print(f"  Participant {idx}: ERROR — {e}")

    if sus_scores:
        stats = compute_statistics(sus_scores)
        print(f"\n--- Aggregate Statistics ---")
        print(f"  N: {stats['n']}")
        print(f"  Mean: {stats['mean']}")
        print(f"  Std Dev: {stats['std_dev']}")
        print(f"  Median: {stats['median']}")
        print(f"  Min: {stats['min']} / Max: {stats['max']}")
        print(f"  Above average (>= 68): {'Yes' if stats['above_average'] else 'No'}")

        if stats["n"] < 15:
            print(f"\n  Warning: n={stats['n']} is below the recommended minimum of 15 participants.")

        report_dir = Path("eval_reports")
        report_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"sus_{timestamp}.json"
        with open(report_path, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "items": SUS_ITEMS,
                "per_participant": results,
                "statistics": stats,
            }, f, indent=2)
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    import sys
    main()
