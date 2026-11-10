# DocIntel AI — Evaluation Scripts

This directory contains scripts for running the academic evaluation of the DocIntel AI document editor. No live measurements have been performed yet. These scripts are instruments ready for use when evaluation is approved.

## Prerequisites

Install the evaluation dependencies (not included in the main requirements):

```bash
cd backend
venv/bin/pip install locust textstat language-tool-python scipy numpy
```

Note: `language-tool-python` requires Java 8+ installed on the system. The first run downloads LanguageTool (~200MB).

## Scripts

### 1. Load Test (`load_test.py`)

Measures backend endpoint latency under simulated user load using Locust.

```bash
# Start the backend first
venv/bin/uvicorn app.main:app --port 8000

# Get a Firebase ID token from the browser (localStorage or auth interceptor)
export DOCINTEL_TOKEN="eyJ..."
export DOCINTEL_DOC_ID="some-document-id"  # optional; auto-discovers if omitted

# Run the load test
venv/bin/locust -f scripts/eval/load_test.py --host http://127.0.0.1:8000
```

Open http://localhost:8089 to configure users and spawn rate. Results show p50/p95 latency per endpoint. Cross-reference with `GET /metrics/summary` for server-side latency.

**Targets**: p95 < 500ms for read endpoints, p95 < 1500ms for AI actions.

### 2. Quality Analysis (`quality_analysis.py`)

Compares pre-AI and post-AI document versions for readability and grammar.

```bash
# Single pair
venv/bin/python scripts/eval/quality_analysis.py --before before.json --after after.json

# Multiple pairs
venv/bin/python scripts/eval/quality_analysis.py --pairs pairs.json
```

Export document JSON via the API:
```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/documents/<id> > doc.json
```

**Targets**: readability improvement >= 10%, grammar errors reduced >= 30%.

### 3. SUS Scoring (`sus_scoring.py`)

Scores System Usability Scale questionnaire responses.

```bash
venv/bin/python scripts/eval/sus_scoring.py --responses sus_responses.json
```

See `sus_responses_template.json` for the expected format (array of 10-value arrays, values 1-5).

**Target**: SUS >= 68 (above average). Minimum n = 15 participants.

### 4. Productivity Analysis (`productivity_analysis.py`)

Analyzes words-per-minute (WPM) and perceived productivity with/without AI assistance.

```bash
venv/bin/python scripts/eval/productivity_analysis.py --data productivity_data.json
```

See `productivity_data_template.json` for the expected format.

**Targets**: WPM increase >= 15% with AI. Significance threshold alpha = 0.05. Minimum n = 15 participants.

## Evaluation Workflow

1. **Recruit participants** (minimum 15 for usability, 30 documents for quality analysis).
2. **Scripted task set**: register, create a document, write 200+ words, use 3 AI actions, accept/reject a suggestion, save a named version, restore a version, share with a collaborator, view shared document.
3. **Administer SUS questionnaire** after the task set. Score with `sus_scoring.py`.
4. **Run load test** with Locust to measure backend performance. Use `GET /metrics/summary` for server-side p50/p95.
5. **Collect document pairs** (before/after AI actions) and run `quality_analysis.py`.
6. **Run productivity sessions** (10-minute free writing with/without AI) and analyze with `productivity_analysis.py`.
7. **Export frontend metrics** from the sidebar's "Export data" button for keystroke/action counts.
8. **Statistical analysis**: paired t-test (or Wilcoxon if n < 30), Cohen's d, alpha = 0.05.

## Output

All scripts save JSON reports to `backend/eval_reports/` with timestamps. Do not commit evaluation reports with real participant data — add `eval_reports/` to `.gitignore` if collecting real data.

## Current Status

- Scripts are created and ready to use.
- No participant data has been collected.
- No results have been measured.
- Do not claim any evaluation results without actual measurements.
