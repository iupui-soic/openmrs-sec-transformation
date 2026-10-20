# Qualitative data

Meeting passages and coding for RQ1 and RQ2.

| File | Contents |
|---|---|
| `codebook.md` | The codebook (three questions per passage) |
| `practice.csv` | Nine practice passages with answers and reasons, given to both coders |
| `passages.csv` | The 120 coded passages: id, meeting date, source type (transcript or written notes), text |
| `codes_CH.csv`, `codes_NPN.csv` | Each coder's codes, as submitted |
| `agreement.py` | Computes Cohen's kappa and the agreed sets used in the paper (standard library only) |
| `agreement_results.md` | Output of `agreement.py` |
| `agreed_rq1.csv` | 33 passages both coders coded Decided or Done (RQ1) |
| `agreed_rq2.csv` | 27 passages both coders gave the same barrier or enabler kind (RQ2) |

Run: `python3 qual/agreement.py`

## Notes

- Passages come from transcripts and written notes of 26 working group meetings,
  March 26 to September 3, 2026. Every person's name is replaced with `[name]`, and
  speakers are numbered within each passage. The full transcripts and notes are
  confidential and not included.
- Passages are quoted as spoken, including filler words and transcription errors.
- One detail of an unpublished vulnerability report is removed from S030 and marked
  `[count removed]`.
- Disagreements were not settled. The paper's results use only codes on which both
  coders agreed.
- Three NPN action codes (S014, S018, S020) are not codebook choices. They are kept as
  submitted and count as disagreements.
