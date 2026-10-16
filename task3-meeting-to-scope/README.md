# Task 3: Meeting to Scope & Scope Diff

Multi-agent system for sales meeting transcript analysis, technical feasibility verification, 10-section Scope of Work (SOW) drafting, hours/cost estimation, client proposal generation, and automated scope diffing against approved baselines.

---

## 1. Custom User Transcript Ingestion

You can drop your own meeting transcripts directly into the `transcripts_user/` folder as `.txt` files. They will automatically be parsed, exposed in the Streamlit UI dropdown selector, and processed through the 5-agent pipeline.

### Supported Format
Each line should be formatted as:
```text
Speaker: text
```
or with an optional timestamp:
```text
[00:01:15] Speaker: text
```
- **Timestamps:** Optional (format: `00:01:15`, `[00:01:15]`, or omitted). If omitted, default timestamp `00:00` is assigned.
- **Continuation Lines:** Lines without a `Speaker:` prefix continue the previous speaker's utterance.
- **Comments & Blank Lines:** Lines starting with `#` and empty lines are automatically ignored.

### Sample File: `transcripts_user/sample_call.txt`
```text
[00:01:00] Emily Watson: Hello Alex, thank you for joining our kickoff meeting today.
[00:01:25] Alex Rivera: Good morning Emily! Glad to connect. Let's discuss your key platform goals.
[00:02:10] Emily Watson: We need to import our 500 member law firms via CSV with category tags.
[00:03:00] Alex Rivera: Brilliant Directories supports CSV category and member imports natively.
[00:04:15] Emily Watson: We also need automated email alerts sent to the lead attorney when a client submits a consultation request.
[00:05:00] Alex Rivera: That is handled natively through Email Forwarders and Lead Routing.
[00:06:20] Emily Watson: Great. Can we target launch for November 20, 2026?
[00:07:00] Alex Rivera: Yes, November 20 is confirmed. We will draft the full scope.
```

---

## 2. Staged Chunking & Progressive Merge Engine

For lengthy transcripts (such as 15-minute to 60-minute calls exceeding 40 dialogue turns or 150 lines), the `Transcript Analyst` employs **staged chunking**:

1. **Partitioning:** The dialogue is partitioned into staged windows of 35 turns with an overlap of 5 turns (`staged_chunk_dialogue`).
2. **Staged Extraction:** Each chunk is analyzed independently to extract candidate requirement changes while filtering out conversational pleasantries and consultant repetitions.
3. **Merge & Deduplication Step (`merge_extracted_requirements`):** Candidate statements from all chunks are consolidated, canonicalized by intent, and deduplicated.
4. **Verification Test:** Verified in `tests/test_transcript_chunking.py` against `transcripts_user/test_messy_150lines.txt` (155 lines $\to$ staged chunks $\to$ merge step).

> [!NOTE]
> **Offline Test Classification:** In unit tests and offline testing mode, `test_messy_150lines.txt` is processed via `offline_heuristic` rules to make zero paid LLM calls. This test is explicitly classified as a **staged chunking and merge deduplication test**, and is not an LLM long-transcript extraction evaluation.
