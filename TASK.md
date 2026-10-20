# GES Engineering Onsite Exercise: The Evidence Intake and Readiness Engine

Welcome. Today you will build a small but real piece of GES, review some legacy code, and then
talk the design through with us. The exercise is deliberately larger than the time available.
**We do not expect you to finish.** We want to see how you prioritise, how carefully you handle
the dangerous edge cases, and how you explain your choices. Work through the tiers in order.

Everything is offline and all data is invented. You need only Python 3.10+ and an editor.

## 0. The session

| Time | What happens |
|---|---|
| 0:00 – 0:15 | Read this brief. Ask the interviewer anything about the *logistics*. |
| 0:15 – 2:45 | **Part A: build the engine** (2 h 30 min). |
| 2:45 – 3:10 | **Part B: code review**: write `REVIEW.md` (25 min). |
| 3:10 – 3:45 | **Part C: discussion** with the interviewer: walk through your code, design questions, one small live change. |

Rules:

- Python standard library only. No internet and no AI assistants. Offline Python docs are fine:
  `python -m pydoc -b`.
- When the spec is unclear, **decide, write the decision in `NOTES.md`, and move on.** Choosing
  sensibly is part of the test.
- Keep `NOTES.md` up to date as you go: what works, what does not, what you would do next. When
  time runs out, your code and notes are judged as they are.
- Commit to git as you go if you know git (`git init` first); it helps us follow your thinking.
- It is better to have Tier 1 solid and tested than all tiers half working.

Getting started:

```bash
python tools/make_inbox.py inbox     # generates inbox/day1 and inbox/day2
python -m ges_intake --library library --clients clients run --client C-1001 \
       --inbox inbox/day1 --as-of 2026-03-01 --outbox outbox.jsonl
```

`ges_intake/__main__.py` already parses the arguments and prints the report. Everything behind
`run()` is yours to design.

---

## 1. Context: what GES is

GES (Governed Execution System) is the software that runs the work of an accounting and tax firm
called Peach State. Its central idea is that **the system never guesses**. For every piece of
professional work it asks:

1. What must be proven?
2. What evidence proves it?
3. Is that evidence actually present, trustworthy, and current?
4. Does a CPA have to make a judgment call?
5. What is the system allowed to do next?

Every step is recorded so that any result can be traced back to the evidence behind it.

Four rules explain most of the design. You will see each of them in the requirements below.

- **Information ≠ evidence ≠ fact ≠ professional conclusion ≠ permission to release.** Each is a
  separate step with its own owner.
- **Having it ≠ ready. Finished ≠ approved. Reviewed ≠ released. Automated ≠ authorized.**
- **Anything derived from evidence stays linked to that evidence.**
- **Corrections add new history; they never rewrite old history.**

And the "Answer = 4" rule: if the target is 4 and you can only prove 1, the system does not invent
the other 3. It says precisely that 3 is missing, and asks for it.

### Vocabulary you need

| Term | Meaning |
|---|---|
| **CEL** | Client Evidence Library: the catalogue of evidence *kinds* (e.g. "bank account statement"). Each CEL entry carries governance codes. |
| **Document type** | A concrete document that can serve as a CEL kind (e.g. "Form W-2" → wage statement CEL). |
| **Evidence instance / document** | One specific file a client sent us. |
| **P (provenance)** | Where it came from. P1 official/government, P2 independent third party, P3 client-generated, P4 prepared by the firm. |
| **E (evidence grade)** | How far it can be relied on. E1 direct, E3 client/management-dependent, E4 incomplete or contradictory, E5 prohibited (cannot be used). |
| **C (criticality)** | What rides on it. C1 blocks release, C2 blocks the related conclusion, C3 supports analysis, C4 background. |
| **S (security)** | Sensitivity. S5 is restricted: returns, SSNs, bank data. |
| **PDA** | Professional Determination: one thing that must be established for a service (e.g. "taxpayer identity is established"). A PDA lists the evidence it needs. |
| **Pathway** | An alternative way to satisfy a PDA. A PDA is met if **any** pathway is met; a pathway is met if **all** of its requirements are met. |
| **Service line** | A firm service, e.g. 4A Financial Reconstruction. A service activates a set of PDAs. |
| **Readiness** | Whether the evidence needed for a service is actually present and usable. |
| **Attention (NOW / NEXT / WATCH / NORMAL)** | What each person should look at. One underlying fact is shown differently to each role. |
| **EIC** | Operations staff who chase clients for documents. Not a CPA; makes no professional judgments. |

A worked example from the firm's own notes: a client needs 12 monthly bank statements but sent 6.
Readiness already knows exactly which 6 are missing. The **client** sees "upload your missing
statements" as NOW. The **EIC** sees "six statements outstanding, follow up" as NOW. The **CPA**
sees nothing urgent, because no judgment is needed yet. The **owner** sees nothing. When the
statements arrive, the same item calms down. One truth underneath, different views on top.

---

---

## 2. What you are building

One command that ingests one or more inbox batches **in the order given**, governs every document,
and evaluates readiness for the client's engaged service:

```
 inbox batch (manifest.json + files)
        │
        ▼
 ┌──────────────┐  reject: unsafe path, symlink, too large, wrong type, bad encoding, bad timestamp…
 │ 1. Intake    │──────────────────────────────────────────────────────────────► logged rejection
 └──────┬───────┘
        ▼
 ┌──────────────┐  same bytes already held for this client ─────────────────────► duplicate (no-op)
 │ 2. Identity  │
 └──────┬───────┘
        ▼
 ┌──────────────┐  rule-based fingerprints only. No match / ambiguous ─► review queue
 │ 3. Classify  │                         + advisory suggestion (redacted, never applied)
 └──────┬───────┘
        ▼
 ┌──────────────┐  typed fields, masked identifiers, identity check against the client,
 │ 4. Extract & │  provenance from channel (never from document text), grade, flags
 │    govern    │  identity mismatch ─► quarantine + security incident
 └──────┬───────┘
        ▼
 ┌──────────────┐  corrections supersede older versions (history kept)
 │ 5. Supersede │
 └──────┬───────┘
        ▼
 ┌──────────────┐  PDAs, pathways, currentness, coverage gaps, balance continuity,
 │ 7. Readiness │  dependencies
 └──────┬───────┘
        ▼
 ┌──────────────┐  per-role NOW / NEXT / WATCH; client view leaks nothing internal
 │ 8. Attention │  (stretch)
 └──────────────┘
```

### The tiers

| Tier | Scope | Spec |
|---|---|---|
| **1** | Manifest, intake checks, document IDs, duplicates, classification, field extraction with masking, identity check, provenance, grade, status, exit codes | §4.1–4.6 |
| **2** | Readiness: pathways, currentness, coverage gaps, PDA issues, status precedence, dependencies, service status | §4.9 |
| **3** | Supersession across batches, balance continuity, the advisory classifier with redaction, library validation (unknown references, dependency cycles → exit 2), determinism | §4.7, §4.9, §4.13 |
| Stretch | Attention lists per role | §4.12 |

What is provided:

| Path | What it is |
|---|---|
| `library/` | Synthetic evidence library: 7 CEL kinds, 11 document types, service 4A (5 PDAs), intake policy. |
| `clients/` | Client profiles. C-1001 is the client in the inbox. |
| `tools/make_inbox.py` | Generates the two batches. Read it: it tells you what is in them. |
| `vendor/advisory_stub.py` | Simulated external AI classifier. Do not edit. |
| `review/legacy_tagger.py` | For Part B. Do not edit. |
| `ges_intake/__main__.py` | Argument parsing and output only. |

**The engine must be data-driven.** We also run it on a library and client you have not seen.
Nothing about service 4A, specific PDA, CEL or document-type IDs may be hard-coded in your logic.

---

## 3. Output contract

Exit `0` on success. Exit `2`, with a message on stderr and nothing on stdout, for: a missing or
malformed manifest, a manifest whose `client_id` differs from `--client`, an unknown or malformed
client ID (it must never be used as a path fragment unchecked), or an invalid library. Never open a
network connection, never read the system clock for anything that affects output: two runs on
the same input must print identical bytes in any time zone.

```json
{
  "client_id": "C-1001",
  "as_of": "2026-03-01",
  "batches": [
    {
      "batch_id": "B-2026-02-21-001", "client_id": "C-1001",
      "documents": [{"source": "engagement_letter.txt", "document_id": "DOC-…", "doc_type": "DT-ENGAGEMENT-LETTER",
                     "cel": "CEL-GOV-001", "provenance": "P3", "grade": "E3", "status": "accepted", "flags": []}],
      "duplicates": [{"source": "w2_acme_2025_copy.txt", "document_id": "DOC-…"}],
      "rejected":   [{"source": "empty.txt", "reason": "empty"}],
      "ignored":    ["notes_unlisted.txt"]
    }
  ],
  "documents": [{"document_id": "DOC-…", "status": "superseded"}],
  "readiness": {
    "client_id": "C-1001", "service": "4A", "as_of": "2026-03-01", "library_version": "SYNTH-CEL-1.0",
    "status": "READY | NOT_READY | BLOCKED",
    "security_holds": ["document:DOC-…"],
    "pdas": [{"id": "PDA-A03", "name": "…", "status": "MISSING", "depends_on": [],
              "pathways": [{"name": "bank_statements", "met": false,
                            "missing": [{"cel": "CEL-BNK-001", "account": "4821", "gaps": [["2025-03-01", "2025-03-31"]]}]}],
              "satisfied_by": [], "issues": ["document:DOC-…"]}]
  },
  "attention": {"client": [], "eic": [], "cpa": [], "owner": []}
}
```

- One entry in `batches` per `--inbox`, in order. In a batch, `documents`, `duplicates` and
  `rejected` are in processing order (§4.1); `ignored` and `flags` are sorted. A batch's
  `documents` lists only documents new in that batch, with their status at the end of that batch.
- Top-level `documents`: every document of the client (all batches) with its **final** status,
  sorted by `document_id`.
- In `readiness`, `pdas` and `pathways` follow config order; `satisfied_by` and `issues` are
  sorted. A `missing` entry always has `cel`, plus `account`/`gaps` for coverage requirements.
- Omit `attention` if you do not get to the stretch goal.
- Unclassified documents have `doc_type`, `cel`, `provenance` and `grade` set to `null`.

---

## 4. Detailed rules

### 4.1 Manifest and processing order

`INBOX/manifest.json`:

```json
{"client_id": "C-1001", "batch_id": "B-…",
 "entries": [{"file": "w2.txt", "original_name": "W2.txt", "channel": "portal_upload",
              "received_at": "2026-02-17T10:01:00Z"}]}
```

- If the manifest is missing, is not valid JSON, has no `entries` list, or its `client_id` differs
  from `--client`: exit 2 and change nothing.
- `file` is relative to the inbox and **untrusted**. `original_name` is what the user called the
  file: also untrusted, used for display only, never as a path.
- **Processing order**: entries with a valid `received_at` sorted by (UTC instant, `file`), then
  entries with an invalid timestamp sorted by `file`. Manifest order means nothing.
- Top-level files in the inbox that no entry references (other than `manifest.json`) are reported
  in `ignored` and not read.

### 4.2 Intake checks

Apply in this order. The first failure is the `reason`:

| # | Check | Reason |
|---|---|---|
| 1 | `received_at` is ISO 8601 **with** a UTC offset or `Z` | `invalid_timestamp` |
| 2 | `channel` is in `intake_policy.channels` | `invalid_channel` |
| 3 | `file` is a non-empty relative path with no NUL that resolves inside the inbox directory | `unsafe_path` |
| 4 | the file exists | `missing_file` |
| 5 | it is not a symlink | `symlink` |
| 6 | it is a regular file | `unsafe_path` |
| 7 | its extension (case-insensitive) is in `allowed_extensions` | `unsupported_type` |
| 8 | its size ≤ `max_bytes` | `too_large` |
| 9 | it is not empty | `empty` |
| 10 | it decodes as UTF-8 (a UTF-8 BOM is allowed) | `not_utf8` |

Never read more than `max_bytes + 1` bytes of any file. Never read a file outside the inbox.

### 4.3 Document identity and duplicates

- `sha256` = SHA-256 hex of the file's raw bytes.
- `document_id` = `"DOC-" + sha256_hex(f"{client_id}:{sha256}")[:12]`.
- If the client already has a document with that ID (from this batch or an earlier `--inbox` in the
  same run): it is a **duplicate**. Report it and change nothing.

### 4.4 Normalisation and classification

- **Normalised text**: strip a leading BOM, convert `\r\n` and `\r` to `\n`, apply Unicode NFKC.
- **Phrase view**: normalised text, `casefold()`, every run of whitespace collapsed to one space.
- A document type matches if every phrase in `match.all` occurs in the phrase view (phrases are
  casefolded too) and no phrase in `match.none` does.
- Exactly one match: classified. Zero: flag `no_match`. More than one: flag `ambiguous_type`.
  Unclassified documents are `pending_review` with `doc_type`/`cel`/`provenance`/`grade` null.
  **Do not pick one.**
- The `suspicious_instruction_patterns` (case-insensitive regexes, searched in the phrase view)
  apply to every document, classified or not, and add the flag `suspicious_instructions`.

### 4.5 Field extraction

Each field has a regex `pattern` (compile with `re.MULTILINE | re.IGNORECASE`, search the
normalised text, first match, strip the captured value) and a `type`:

| type | Persisted as | Parsing |
|---|---|---|
| `text` | string | non-empty |
| `date` | `YYYY-MM-DD` | formats `%Y-%m-%d`, `%m/%d/%Y`, `%B %d, %Y` (US order) |
| `date_range` | two fields `<name>_start`, `<name>_end` | two capture groups, each a `date` |
| `money` | decimal string, 2 places (`"-45.20"`) | optional `$`, thousands commas, `-` or `( )` for negative. **Use `Decimal`, never `float`.** |
| `year` | integer | 4 digits |
| `ssn` | `"***-**-1234"` | `123-45-6789`, or a masked form `XXX-XX-1234` / `***-**-1234` |
| `ein` | `"**-***4567"` | `12-3456789` |
| `account` | last 4 digits, e.g. `"4821"` | digits, spaces and dashes; at least 4 digits |

A value that the pattern finds but cannot be parsed adds `unparseable_field` and is treated as
absent. A field in `required_fields` that is absent adds `missing_required_field`. A
`date_range` whose end is before its start adds `invalid_period`.

**Full SSNs, EINs, account, licence and passport numbers must never be persisted or printed
outside the vault.** Only the masked forms above may appear anywhere else.

### 4.6 Identity, provenance, grade, status

Using the document type's `identity` block and the client profile:

1. **SSN check** (`ssn_field`): if the field was parsed and its last 4 digits differ from the
   client's (or it is a full SSN that differs) → flag `identity_mismatch`, grade `E5`,
   provenance null, status `quarantined`, and **persist no extracted fields at all** (they belong to
   someone else). Stop here. This is a security incident.
2. **Name check** (`name_field`): compare with the client's name. Normalise both: NFKC, casefold; if
   there is exactly one comma, treat it as `Last, First Middle` and reorder to `First Middle Last`;
   replace every non-letter with a space; split; drop one-letter tokens. Different token lists →
   `name_mismatch`. (`"RIVERA, JORDAN Q"` matches `"Jordan Q. Rivera"`.)
3. **Account check** (`account_field`): last 4 not in the client's `accounts` → `unknown_account`.
4. **Provenance** comes from the document type and the *channel*, never from anything the document
   says about itself: `by_channel[channel]` if present, else `default`. If the type has
   `claims_official: true` and the channel is not in `by_channel`, add the informational flag
   `claimed_official_source_unverified`.
5. **Grade**: `E5` as above; `E4` if any flag is in `e4_flags`; otherwise `E1` for P1/P2 and `E3`
   for P3.
6. **Status**: `quarantined` (E5), else `pending_review` if any flag is in `review_flags`, else
   `accepted`. The only other status is `superseded` (§4.7).

### 4.7 Supersession (corrections) (Tier 3)

Document X **supersedes** document Y (same client) when all of the following hold:

- X's type has a `supersede` block and Y's type is in its `supersedes` list;
- every field named in X's `supersede.key` is present in X and equal in Y;
- (X.received_at, X.document_id) > (Y.received_at, Y.document_id).

Neither may be `quarantined`. A superseded document keeps its history but
no longer counts as evidence and no longer raises a review issue. The relation depends on
`received_at`, **not** on the order you happen to ingest: a correction received earlier than the
version you already hold arrives as `superseded`.

### 4.9 Readiness (Tier 2; balance continuity is Tier 3)

Evaluate for the given client, service and `as_of`. The engagement period comes from the client
profile. Only `accepted` documents count as evidence.

A document is **usable** for a requirement when: its `cel` is the requirement's CEL; its grade is
in `accepted_grades`; its provenance is in the CEL's `allowed_provenance` and (if given) in the
requirement's `provenance`; and it is **current** under the CEL's `currentness` rule:

| rule | Current when |
|---|---|
| `none` | always |
| `not_expired` | `expiration` ≥ `as_of` (expiring *on* `as_of` is still current) |
| `tax_year` | `tax_year` = (year of engagement `period_end`) + `offset` |
| `period_overlap` | `[period_start, period_end]` overlaps the engagement period |

A requirement is met:

- **no `coverage`**: at least one usable document. Otherwise missing `{"cel"}`.
- **`engagement_period`**: the union of usable documents' periods covers every day of the engagement
  period. Otherwise missing `{"cel", "gaps"}`.
- **`engagement_period_per_account`**: for **each** account in the client profile (profile order),
  the usable documents for that account cover every day. Otherwise one missing
  `{"cel", "account", "gaps"}` per account. An account with nothing gets the whole period.

`gaps` are inclusive `[start, end]` date pairs, ascending, merged.

**Balance continuity** (per-account coverage only): for each account, sort its usable statements
by (`period_start`, `period_end`, `document_id`). For each consecutive pair (a, b) where
`b.period_start` is exactly the day after `a.period_end`, if `b.beginning_balance` ≠
`a.ending_balance` (as decimals) there is an issue `balance_discontinuity:<account>:<b.period_start>`.
Pairs that are not adjacent are not compared.

**PDA issues**: unresolved balance discontinuities from its requirements, plus
`document:<document_id>` for every `pending_review` document whose CEL appears in **any** of the
PDA's requirements. A pending document can stop a determination even when another pathway is met:
someone must look at it first.

**PDA status** (first rule that applies):

1. `MISSING`: no pathway met.
2. `PENDING_REVIEW`: there are issues.
3. `BLOCKED_BY_DEPENDENCY`: some `depends_on` PDA is not `SATISFIED`/`READY_FOR_DETERMINATION`.
4. `READY_FOR_DETERMINATION` if `requires_cpa`, else `SATISFIED`. The engine never makes the
   CPA's determination itself.

`satisfied_by`: sorted, de-duplicated IDs of the usable documents of the **first** met pathway (for
per-account coverage, those for profile accounts). Empty if none met.

**Service status**: `BLOCKED` if the client has any `quarantined` document (these are listed in
`security_holds` as `document:<id>`); else `READY` if every PDA is `SATISFIED` or
`READY_FOR_DETERMINATION`; else `NOT_READY`.

### 4.12 Attention (stretch goal: only if Tiers 1–3 are done)

Computed for the client's engaged service and returned under `attention` as `{"client": [...], "eic": [...], "cpa": [...], "owner": [...]}`. With no review command onsite, every `pending_review` document and unresolved discontinuity is an open review issue.

| Condition | client | eic | cpa | owner |
|---|---|---|---|---|
| Missing evidence (from the **first** pathway of each `MISSING` PDA), CEL criticality C1 | NOW | NOW | | |
| Same, criticality C2 or C3 (C4: nothing) | NEXT | NEXT | | |
| Open review issue (`review_required`) | | NOW | WATCH | |
| Quarantined document (`security_incident`) | | NOW | WATCH | NOW |
| PDA `READY_FOR_DETERMINATION` | | | NOW | |
| PDA `BLOCKED_BY_DEPENDENCY` | | | WATCH | |

- `kind` ∈ `missing_evidence`, `review_required`, `security_incident`, `ready_for_determination`,
  `blocked_by_dependency`.
- `key`: `missing:<CEL id>`, `issue:<issue id>`, `pda:<PDA id>`. **One item per key per role**:
  a CEL missing from three PDAs is one item, with all its gaps.
- Order: level (NOW, NEXT, WATCH), then `kind`, then `key`.
- **Client items have no `key`**, and nothing a client sees may contain internal codes (PDA, CEL,
  DT or DOC identifiers, P/E/C/S/RU/RV codes), anything about other people, or words such as
  quarantine. Use the CEL's `client_label`, and say exactly what is missing (dates, account
  ending).
- Messages for staff are your choice, but must be useful and must follow §4.5.

### 4.13 The advisory classifier (Tier 3)

`vendor/advisory_stub.request_suggestion(text, outbox_path)` simulates sending text to an external
AI model. Its answers are unreliable, sometimes confidently wrong.

- Call it for **every** document that is unclassified (`no_match`/`ambiguous_type`), with
  `outbox_path` = the `--outbox` argument.
- The text you send leaves the firm. **Redact it first**; no identifier from §4.5 may reach the
  outbox.
- Record the suggestion on the document for the reviewer. It must **never** change a
  classification, provenance, grade, status or readiness.


---

## 5. Self-check: day 1

Running day 1 alone at `--as-of 2026-03-01`, batch 1 should have 20 documents, 1 duplicate,
8 rejections and 1 ignored file, and readiness should show:

| PDA | Status | Why |
|---|---|---|
| PDA-A01 | SATISFIED | Signed engagement letter (P3 gives E3, which is accepted). |
| PDA-A02 | MISSING | The driver's licence expired 2026-02-28. The "official" transcript was uploaded by the client, so it is P3, not P1. |
| PDA-A03 | MISSING | Account 4821 is missing 2025-03-01 to 2025-03-31; account 9930 is missing 2025-02-28. |
| PDA-A04 | PENDING_REVIEW | A W-2 meets the PDA, but a 1099 containing suspicious instructions needs review. |
| PDA-A05 | BLOCKED_BY_DEPENDENCY | Its own ledger evidence is fine; it waits for PDA-A03. |

The service is `BLOCKED`: a document belonging to another taxpayer arrived in this client's batch.
Day 2 brings corrections and the missing pieces; work out what should happen.

---

## 6. Part B: code review (25 minutes, `REVIEW.md`)

`review/legacy_tagger.py` is legacy code a teammate wants to keep using on real client data.
Review it like a pull request. For each finding: line(s), what is wrong, a concrete way it fails,
and severity (critical / high / medium / low). Put the most serious first. Finish with two or
three sentences: should it stay in production while it is replaced, and what would you do first?
Do not rewrite the file.

## 7. Part C: discussion (35 minutes)

No preparation needed. Expect to walk us through one document's journey in your code, answer a
few design questions (for example: how this would run with a queue, a database and a real AI
model, and how you would keep client data separated), and make one small change live.

## 8. How we evaluate

| Area | Weight |
|---|---|
| Automated acceptance tests (Tier 1 heaviest, then 2, then 3) | 55 |
| Code quality: structure, clear stages, honest error handling, `Decimal`/`date` types, tests you wrote | 15 |
| Code review (Part B) | 15 |
| Discussion (Part C) | 15 |
| Stretch goal | +5 bonus |

What costs the most: a full SSN or account number printed anywhere, trusting the AI suggestion,
reading a file outside the inbox, guessing a document type, provenance taken from the document's
own text, and hard-coded IDs.

Good luck.
