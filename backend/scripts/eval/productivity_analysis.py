"""Productivity analysis for academic evaluation.

Compares words-per-minute (WPM) and perceived productivity with and without
AI assistance during a 10-minute free-writing session.

Prerequisites:
    pip install scipy numpy

Usage:
    cd backend
    venv/bin/python scripts/eval/productivity_analysis.py --data productivity_data.json

    Where productivity_data.json contains:
    [
      {
        "participant_id": "p1",
        "without_ai": {"wpm": 12.5, "perceived": 4},
        "with_ai": {"wpm": 15.2, "perceived": 6}
      },
      ...
    ]

    perceived: 1-7 scale (1=not productive at all, 7=extremely productive)

Output:
    Prints paired t-test results and saves a JSON report.

Targets (from evaluation plan):
    - WPM increase >= 15% with AI
    - Significance threshold alpha = 0.05
    - Minimum n = 15 participants (but script works with any n)
"""
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path


def paired_t_test(before: list[float], after: list[float]) -> dict:
    """Compute paired t-test manually (avoids scipy dependency for basic case)."""
    n = len(before)
    if n != len(after):
        raise ValueError("Before and after lists must have the same length")
    if n < 2:
        return {"n": n, "error": "Need at least 2 pairs for t-test"}

    diffs = [after[i] - before[i] for i in range(n)]
    mean_diff = sum(diffs) / n
    variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
    std_diff = math.sqrt(variance)
    se = std_diff / math.sqrt(n)

    if se == 0:
        if mean_diff == 0:
            t_stat = 0.0
            p_value = 1.0
        else:
            # All diffs are identical and non-zero → t is infinite, p ~ 0
            t_stat = float("inf") if mean_diff > 0 else float("-inf")
            p_value = 0.0
    else:
        t_stat = mean_diff / se
        try:
            from scipy import stats as scipy_stats
            t_stat_scipy, p_value = scipy_stats.ttest_rel(after, before)
            t_stat = float(t_stat_scipy)
            p_value = float(p_value)
        except ImportError:
            p_value = 2 * (1 - _normal_cdf(abs(t_stat)))

    cohen_d = mean_diff / std_diff if std_diff > 0 else (float("inf") if mean_diff != 0 else 0)

    return {
        "n": n,
        "mean_diff": round(mean_diff, 4),
        "std_diff": round(std_diff, 4),
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_value, 6),
        "cohen_d": round(cohen_d, 4),
        "significant": p_value < 0.05,
        "alpha": 0.05,
    }


def _normal_cdf(x: float) -> float:
    """Approximate normal CDF using error function."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def main():
    parser = argparse.ArgumentParser(description="Analyze productivity data (WPM with/without AI).")
    parser.add_argument("--data", required=True, help="Path to JSON file with productivity data")
    args = parser.parse_args()

    with open(args.data) as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Error: data file must be a JSON array of participant records")
        sys.exit(1)

    without_wpm = [d["without_ai"]["wpm"] for d in data]
    with_wpm = [d["with_ai"]["wpm"] for d in data]
    without_perceived = [d["without_ai"]["perceived"] for d in data]
    with_perceived = [d["with_ai"]["perceived"] for d in data]

    print(f"Productivity Analysis — {len(data)} participant(s)\n")

    # WPM analysis
    avg_without = sum(without_wpm) / len(without_wpm)
    avg_with = sum(with_wpm) / len(with_wpm)
    pct_increase = ((avg_with - avg_without) / avg_without) * 100 if avg_without > 0 else 0

    print("--- Words Per Minute (WPM) ---")
    print(f"  Avg without AI: {avg_without:.2f} WPM")
    print(f"  Avg with AI: {avg_with:.2f} WPM")
    print(f"  Increase: {pct_increase:.1f}%")

    wpm_stats = paired_t_test(without_wpm, with_wpm)
    print(f"  Paired t-test: t={wpm_stats['t_statistic']}, p={wpm_stats['p_value']}")
    print(f"  Cohen's d: {wpm_stats['cohen_d']}")
    print(f"  Significant (p < 0.05): {'Yes' if wpm_stats['significant'] else 'No'}")
    print(f"  Target (>= 15% increase): {'Met' if pct_increase >= 15 else 'Not met'}")

    # Perceived productivity
    avg_p_without = sum(without_perceived) / len(without_perceived)
    avg_p_with = sum(with_perceived) / len(with_perceived)

    print("\n--- Perceived Productivity (1-7 scale) ---")
    print(f"  Avg without AI: {avg_p_without:.2f}")
    print(f"  Avg with AI: {avg_p_with:.2f}")

    perceived_stats = paired_t_test(without_perceived, with_perceived)
    print(f"  Paired t-test: t={perceived_stats['t_statistic']}, p={perceived_stats['p_value']}")
    print(f"  Cohen's d: {perceived_stats['cohen_d']}")
    print(f"  Significant (p < 0.05): {'Yes' if perceived_stats['significant'] else 'No'}")

    if len(data) < 15:
        print(f"\n  Warning: n={len(data)} is below the recommended minimum of 15 participants.")

    # Save report
    report_dir = Path("eval_reports")
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"productivity_{timestamp}.json"
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "n": len(data),
            "wpm": {
                "avg_without_ai": round(avg_without, 2),
                "avg_with_ai": round(avg_with, 2),
                "pct_increase": round(pct_increase, 1),
                "target_met": pct_increase >= 15,
                "t_test": wpm_stats,
            },
            "perceived": {
                "avg_without_ai": round(avg_p_without, 2),
                "avg_with_ai": round(avg_p_with, 2),
                "t_test": perceived_stats,
            },
        }, f, indent=2)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
