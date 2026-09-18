# AI Proof API

A minimal FastAPI + SQLite service that makes an AI request/response record **tamper-evident after the fact**.

The API stores each record with a SHA-256 receipt. Every receipt includes the hash of the previous record, creating a running hash chain.

## What it does

- Stores an AI request and response.
- Generates a SHA-256 receipt for the stored content.
- Links each receipt to the previous receipt.
- Verifies whether a stored record still matches its receipt and chain link.
- Reports exactly which integrity check broke when a record is modified.

It does **not** judge whether an AI response is correct.

## Project structure

```text
ai-proof-api/
├── app/
│   ├── __init__.py
│   ├── database.py
│   └── main.py
├── tests/
│   └── test_api.py
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

## Run locally

Python 3.11+ is recommended.

### 1. Create a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the API

```bash
uvicorn app.main:app --reload
```

The API is available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## API

### POST `/records`

Example:

```bash
curl -X POST http://127.0.0.1:8000/records ^
  -H "Content-Type: application/json" ^
  -d "{\"request\":\"What is Python?\",\"response\":\"Python is a programming language.\"}"
```

On macOS/Linux, use:

```bash
curl -X POST http://127.0.0.1:8000/records \
  -H "Content-Type: application/json" \
  -d '{"request":"What is Python?","response":"Python is a programming language."}'
```

Example response:

```json
{
  "id": 1,
  "receipt": "8f...",
  "previous_receipt": null,
  "created_at": "2026-09-18T08:30:00+00:00"
}
```

For the next record, `previous_receipt` contains the receipt of record 1.

## Verify a record

```bash
curl http://127.0.0.1:8000/verify/1
```

Before tampering:

```json
{
  "valid": true,
  "record_id": 1,
  "message": "Record is intact.",
  "broken": []
}
```

## Tampering demonstration

This is the important part of the implementation.

### 1. Create a record

Create record 1 using the POST endpoint and note its `id`.

### 2. Verify it

```bash
curl http://127.0.0.1:8000/verify/1
```

It should return:

```json
{
  "valid": true,
  "record_id": 1,
  "message": "Record is intact.",
  "broken": []
}
```

### 3. Tamper with the SQLite database

Stop the server if desired, then open `records.db` using a SQLite client.

For example:

```sql
UPDATE records
SET response = 'This was changed after the record was written.'
WHERE id = 1;
```

Do not update `content_hash`.

### 4. Verify again

```bash
curl http://127.0.0.1:8000/verify/1
```

Now verification should fail:

```json
{
  "valid": false,
  "record_id": 1,
  "message": "Record was altered.",
  "broken": [
    "content_hash"
  ]
}
```

The stored response no longer produces the stored SHA-256 receipt.

### Chain-link tampering

For record 2, the receipt is calculated using record 1's receipt:

```text
Record 1
   content_hash = AAA
          ↓
Record 2
   previous_hash = AAA
   content_hash  = BBB
          ↓
Record 3
   previous_hash = BBB
```

If the `previous_hash` of record 2 is changed, verification reports both the changed content hash and broken chain link.

This is also covered by the automated test suite.

## How the receipt works

For every record:

```text
request
response
created_at
previous_hash
       │
       ▼
canonical representation
       │
       ▼
SHA-256
       │
       ▼
content_hash / receipt
```

The receipt for record `N` includes the receipt from record `N-1`.

Therefore, changing a record without rebuilding the chain causes verification to fail.

The implementation uses length-prefixed fields when constructing the hash input rather than simply joining strings with a delimiter. This avoids simple delimiter-collision ambiguities.

## What this proves

A successful verification proves that:

1. The current stored request, response, timestamp, and previous hash produce the stored SHA-256 receipt.
2. The record's previous-hash link agrees with the previous stored record.
3. No modification covered by those checks has occurred without recomputing the corresponding hash values.

If someone changes a stored response and leaves the receipt unchanged, the API catches it.

## What this does NOT prove

This is a **tamper-evident hash chain**, not a complete cryptographic audit system.

It does not prove:

- that the AI response is correct or truthful;
- that a particular AI model generated the response;
- who originally submitted the record;
- that the original database itself was trustworthy;
- that an attacker with unrestricted database access cannot rewrite every record and recompute the entire chain.

There are no accounts, signing keys, or external trust anchors in this project, intentionally.

For stronger production guarantees, receipts could be digitally signed and/or periodically anchored outside the database (for example, in a separate trusted append-only system). Access controls and authenticated identities would also be needed.

## Growth and performance

Adding one record requires:

- reading the latest receipt;
- calculating one SHA-256 hash;
- inserting one SQLite row.

That is approximately constant work per new record.

Verification of an individual record is also approximately constant-time with the current indexed primary-key lookup, although a full historical audit of all records is **O(n)**.

To measure behavior as the system grows, I would benchmark datasets such as:

```text
1,000 records
10,000 records
100,000 records
1,000,000 records
```

For each size, measure:

- record insertion throughput;
- single-record verification latency;
- full-chain verification time;
- SQLite database size.

A production implementation would also consider batching, database WAL mode, append-only storage, checkpointing, and external anchoring depending on the required threat model.

## Tests

Run:

```bash
pytest -q
```

The tests cover:

- normal record creation and verification;
- changing a stored response;
- changing a chain link.

The tampering test directly modifies the SQLite database and confirms that the API reports the record as invalid.

## Docker

Build:

```bash
docker build -t ai-proof-api .
```

Run:

```bash
docker run --rm -p 8000:8000 ai-proof-api
```

Then open:

```text
http://127.0.0.1:8000/docs
```

## Design choice

The project deliberately avoids accounts, authentication, real signing keys, blockchain infrastructure, and other features outside the requested scope.

The goal is a small, understandable implementation where the core property — **a stored AI record can be checked later and an unnoticed modification is detected** — is easy to inspect and test.
