"""Document quality analysis for academic evaluation.

Compares pre-AI and post-AI document versions using:
    1. Word count delta
    2. Readability score (Flesch-Kincaid via textstat)
    3. Grammar error count (via language_tool_python)

Prerequisites:
    pip install textstat language-tool-python

    Note: language-tool-python requires Java 8+ installed on the system.
    The first run will download LanguageTool (~200MB).

Usage:
    cd backend
    venv/bin/python scripts/eval/quality_analysis.py --before <pre_ai.json> --after <post_ai.json>

    Where pre_ai.json and post_ai.json are exported document content (ProseMirror JSON).
    You can export from the editor's stats panel or via the API:

    curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/documents/<id> > doc.json

    Or analyze multiple pairs:
    venv/bin/python scripts/eval/quality_analysis.py --pairs pairs.json

    Where pairs.json is: [{"before": "path/to/before1.json", "after": "path/to/after1.json"}, ...]

Output:
    Prints a table of metrics and saves a JSON report to eval_reports/quality_<timestamp>.json

Targets (from evaluation plan):
    - Readability improvement >= 10%
    - Grammar errors reduced >= 30%
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def prosemirror_to_text(content: dict) -> str:
    """Extract plain text from ProseMirror JSON content."""
    if not content or not isinstance(content, dict):
        return ""
    parts: list[str] = []

    def walk(node: dict) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "text" and "text" in node:
            parts.append(node["text"])
        if "content" in node and isinstance(node["content"], list):
            for child in node["content"]:
                walk(child)
        if node.get("type") == "paragraph":
            parts.append("\n")

    walk(content)
    return " ".join(parts).strip()


def compute_readability(text: str) -> dict:
    """Compute readability metrics using textstat."""
    try:
        import textstat
    except ImportError:
        return {"error": "textstat not installed. Run: pip install textstat"}
    return {
        "flesch_reading_ease": round(textstat.flesch_reading_ease(text), 2),
        "flesch_kincaid_grade": round(textstat.flesch_kincaid_grade(text), 2),
        "automated_readability_index": round(textstat.automated_readability_index(text), 2),
        "coleman_liau_index": round(textstat.coleman_liau_index(text), 2),
        "smog_index": round(textstat.smog_index(text), 2),
        "word_count": textstat.lexicon_count(text),
        "sentence_count": textstat.sentence_count(text),
        "syllable_count": textstat.syllable_count(text),
    }


def check_grammar(text: str) -> dict:
    """Check grammar errors using language_tool_python."""
    try:
        import language_tool_python
    except ImportError:
        return {"error": "language_tool_python not installed. Run: pip install language-tool-python"}
    tool = language_tool_python.LanguageTool("en-US")
    matches = tool.check(text)
    tool.close()
    return {
        "error_count": len(matches),
        "errors": [
            {
                "rule": m.ruleId,
                "message": m.message,
                "context": m.context[:100],
                "offset": m.offset,
            }
            for m in matches
        ],
    }


def analyze_pair(before_path: str, after_path: str) -> dict:
    """Analyze a before/after document pair."""
    with open(before_path) as f:
        before_content = json.load(f)
    with open(after_path) as f:
        after_content = json.load(f)

    before_text = prosemirror_to_text(before_content.get("content", before_content))
    after_text = prosemirror_to_text(after_content.get("content", after_content))

    before_readability = compute_readability(before_text)
    after_readability = compute_readability(after_text)
    before_grammar = check_grammar(before_text)
    after_grammar = check_grammar(after_text)

    deltas: dict = {}
    if "error" not in before_readability and "error" not in after_readability:
        for key in ["flesch_reading_ease", "flesch_kincaid_grade", "word_count"]:
            deltas[key] = round(after_readability[key] - before_readability[key], 2)
        if before_readability["flesch_reading_ease"] != 0:
            deltas["readability_pct_change"] = round(
                ((after_readability["flesch_reading_ease"] - before_readability["flesch_reading_ease"])
                 / abs(before_readability["flesch_reading_ease"])) * 100,
                2,
            )
    if "error" not in before_grammar and "error" not in after_grammar:
        deltas["grammar_error_delta"] = after_grammar["error_count"] - before_grammar["error_count"]
        if before_grammar["error_count"] > 0:
            deltas["grammar_error_pct_change"] = round(
                ((after_grammar["error_count"] - before_grammar["error_count"])
                 / before_grammar["error_count"]) * 100,
                2,
            )

    return {
        "before_file": before_path,
        "after_file": after_path,
        "before_readability": before_readability,
        "after_readability": after_readability,
        "before_grammar": before_grammar,
        "after_grammar": after_grammar,
        "deltas": deltas,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze document quality before/after AI actions.")
    parser.add_argument("--before", help="Path to pre-AI document JSON")
    parser.add_argument("--after", help="Path to post-AI document JSON")
    parser.add_argument("--pairs", help="Path to JSON file with list of {before, after} pairs")
    args = parser.parse_args()

    if args.pairs:
        with open(args.pairs) as f:
            pairs = json.load(f)
    elif args.before and args.after:
        pairs = [{"before": args.before, "after": args.after}]
    else:
        parser.error("Provide --before and --after, or --pairs")

    results = []
    for pair in pairs:
        print(f"\nAnalyzing: {pair['before']} -> {pair['after']}")
        result = analyze_pair(pair["before"], pair["after"])
        results.append(result)

        d = result["deltas"]
        print(f"  Word count delta: {d.get('word_count', 'N/A')}")
        print(f"  Readability (Flesch) delta: {d.get('flesch_reading_ease', 'N/A')}")
        print(f"  Readability % change: {d.get('readability_pct_change', 'N/A')}%")
        print(f"  Grammar error delta: {d.get('grammar_error_delta', 'N/A')}")
        print(f"  Grammar error % change: {d.get('grammar_error_pct_change', 'N/A')}%")

    if len(results) > 1:
        readability_changes = [r["deltas"].get("readability_pct_change", 0) for r in results if "readability_pct_change" in r["deltas"]]
        grammar_changes = [r["deltas"].get("grammar_error_pct_change", 0) for r in results if "grammar_error_pct_change" in r["deltas"]]
        print("\n--- Aggregate ---")
        if readability_changes:
            print(f"  Avg readability % change: {sum(readability_changes) / len(readability_changes):.2f}%")
        if grammar_changes:
            print(f"  Avg grammar error % change: {sum(grammar_changes) / len(grammar_changes):.2f}%")

    report_dir = Path("eval_reports")
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"quality_{timestamp}.json"
    with open(report_path, "w") as f:
        json.dump({"timestamp": timestamp, "results": results}, f, indent=2)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
