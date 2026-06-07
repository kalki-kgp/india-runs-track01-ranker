#!/usr/bin/env python3
"""Streamlit sandbox for running the Redrob ranker on small samples."""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

import streamlit as st

from rank import rank_candidates


ROOT = Path(__file__).resolve().parent
SAMPLE_PATH = ROOT / "sample_candidates.json"


def records_from_json_bytes(data: bytes) -> list[dict]:
    payload = json.loads(data.decode("utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        return payload["candidates"]
    raise ValueError("JSON input must be a candidate list or an object with a candidates list.")


def write_records_as_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")


def uploaded_to_jsonl(uploaded_file, jsonl_path: Path) -> int:
    data = uploaded_file.read()
    name = uploaded_file.name.lower()

    if name.endswith(".jsonl"):
        text = data.decode("utf-8")
        count = 0
        with jsonl_path.open("w", encoding="utf-8") as f:
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
                    f.write(line.strip() + "\n")
                    count += 1
        return count

    records = records_from_json_bytes(data)
    write_records_as_jsonl(records, jsonl_path)
    return len(records)


def load_sample_to_jsonl(jsonl_path: Path) -> int:
    records = records_from_json_bytes(SAMPLE_PATH.read_bytes())
    write_records_as_jsonl(records, jsonl_path)
    return len(records)


def read_csv_rows(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


st.set_page_config(page_title="Redrob Candidate Ranker", page_icon=".", layout="wide")

st.title("Redrob Candidate Ranker")
st.caption("Offline deterministic ranker for Track 01 sample-sized sandbox runs.")

uploaded = st.file_uploader(
    "Upload a small candidate sample",
    type=["json", "jsonl"],
    help="Use a JSON list, JSONL file, or the bundled sample_candidates.json shape.",
)

use_sample = st.checkbox("Use bundled sample_candidates.json", value=uploaded is None)

if st.button("Run ranker", type="primary"):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        jsonl_path = tmp / "candidates.jsonl"
        output_path = tmp / "ranked_candidates.csv"

        try:
            if uploaded is not None:
                candidate_count = uploaded_to_jsonl(uploaded, jsonl_path)
            elif use_sample:
                candidate_count = load_sample_to_jsonl(jsonl_path)
            else:
                st.warning("Upload a sample file or enable the bundled sample.")
                st.stop()

            rank_candidates(str(jsonl_path), str(output_path))
            rows = read_csv_rows(output_path)
            csv_bytes = output_path.read_bytes()

        except Exception as exc:  # pragma: no cover - UI guardrail
            st.error(f"Ranking failed: {exc}")
            st.stop()

    st.success(f"Ranked {len(rows)} candidates from {candidate_count} input records.")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name="ranked_candidates.csv",
        mime="text/csv",
    )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    if len(rows) < min(candidate_count, 100):
        st.info("Some records may have been excluded by honeypot detection.")
