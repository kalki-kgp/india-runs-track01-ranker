# Redrob Track 01 Candidate Ranker

Solo submission scaffold for **India Runs by Redrob AI - Track 01: The Data & AI Challenge / Intelligent Candidate Discovery**.

The task is to rank the top 100 candidates for the supplied **Senior AI Engineer - Founding Team** job description. The ranker reads `candidates.jsonl`, scores each profile offline, and writes a CSV in the required format:

```text
candidate_id,rank,score,reasoning
```

## Why This Approach

The challenge is not just keyword matching. The dataset contains keyword-stuffed profiles, behavioral availability traps, and honeypot profiles with structurally impossible claims. This solution uses a deterministic scoring pipeline so the same input always produces the same ranked output within the CPU-only runtime budget.

The model combines:

- title relevance for direct role fit and keyword-stuffer resistance
- career-history evidence for ranking, retrieval, search, recommendation, embeddings, and production ML systems
- skill fit across retrieval/search, ML core, LLM fine-tuning, ML engineering, and infra taxonomies
- behavioral signals such as recent activity, open-to-work status, response rate, notice period, GitHub activity, and interview completion
- experience, location, and education fit
- honeypot and impossible-profile detection before final ranking

No hosted LLM calls, network access, GPU, or external model downloads are used during ranking.

## Files

- `rank.py` - main offline ranking pipeline
- `submission.csv` - current validated top-100 output
- `validate_submission.py` - provided CSV format validator
- `app.py` - small Streamlit demo/sandbox app for sample-sized candidate files
- `requirements.txt` - dependencies for the demo app only
- `submission_metadata.yaml` - portal metadata draft; contact fields still need to be filled
- `Dockerfile` - optional sandbox container for the Streamlit demo

Large local inputs and exploratory artifacts are intentionally ignored by git:

- `candidates.jsonl`
- `condensed_*.json`
- `llm_candidates_part*.txt`
- `llm_submission.csv`

## Reproduce The Submission

Put the released candidate pool at the repo root as `candidates.jsonl`, then run:

```bash
python3 rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

Validate:

```bash
python3 validate_submission.py ./submission.csv
```

Expected validator result:

```text
Submission is valid.
```

On a MacBook Air M1 with 16 GB RAM, the ranking run completes in roughly 20-30 seconds for 100,000 candidates.

## Demo / Sandbox

For a hosted sandbox, deploy this repo as a Streamlit app and use `app.py` as the entrypoint.

Local demo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Docker demo:

```bash
docker build -t redrob-ranker .
docker run --rm -p 7860:7860 redrob-ranker
```

Then open `http://localhost:7860`.

The demo is meant for small samples, not the full 100K file. The full ranking should be reproduced with the CLI command above.

## Submission Notes

The official Track 01 checklist asks for:

- code repository with complete implementation
- README explaining methodology and architecture
- ranked output CSV in the predefined format
- portal metadata
- sandbox/demo link

Before portal submission, update:

- `submission_metadata.yaml`
- GitHub repository URL
- sandbox URL
- final participant/team name
- contact email and phone

## AI Tools Declaration

AI tools were used for development assistance, architecture discussion, code generation support, and comparison against a pure-LLM ranking baseline. The submitted ranking step itself is deterministic Python and makes no network calls.
