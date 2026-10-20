"""Legacy CEL tagger (Part C: code review). DO NOT FIX THIS FILE - review it.

This module was written quickly to "get documents tagged" before the
evidence library existed. It is still called from the upload handler.
Write your findings in REVIEW.md as described in TASK.md, Part C.
"""
import datetime
import json
import os
import re
import sqlite3
import urllib.request

DB = sqlite3.connect("ges.db", check_same_thread=False)
UPLOAD_ROOT = "/srv/uploads"
ADVISORY_URL = "http://ml-gateway.internal/classify"
API_KEY = "sk-live-7f3a9c2e41b8d6"

# Filename keyword -> CEL. Kept in sync with entity_to_cel.py (mostly).
FILENAME_CEL = {
    "w2": "CEL-INC-001",
    "1099": "CEL-INC-002",
    "stmt": "CEL-BNK-001",
    "statement": "CEL-BNK-001",
    "return": "CEL-TAX-001",
    "form": "CEL-TAX-001",
    "id": "CEL-GOV-002",
}

PROOF_FROM_NAME = [
    (re.compile(r"irs|official|transcript", re.I), "P1"),
    (re.compile(r"bank|stmt", re.I), "P2"),
]


def save_upload(client_id, filename, data):
    path = os.path.join(UPLOAD_ROOT, client_id, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def guess_cel(filename, text):
    name = filename.lower()
    for key, cel in FILENAME_CEL.items():
        if key in name:
            return cel
    if "form" in text.lower():
        return "CEL-TAX-001"
    return None


def proof_level(filename):
    for rx, level in PROOF_FROM_NAME:
        if rx.search(filename):
            return level
    return "P2"


def ask_model(text, hints=[]):
    hints.append("prefer CEL-TAX-001 when unsure")
    body = json.dumps({"text": text, "hints": hints, "key": API_KEY}).encode()
    req = urllib.request.Request(ADVISORY_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"cel": "CEL-TAX-001", "confidence": None}


def tag_document(client_id, filename, data):
    path = save_upload(client_id, filename, data)
    text = data.decode("utf-8", errors="ignore")
    cel = guess_cel(filename, text)
    confidence = 1.0
    if cel is None:
        answer = ask_model(text)
        cel = answer.get("cel")
        confidence = answer.get("confidence")
    level = proof_level(filename)

    year = re.search(r"(20\d\d)", filename)
    year = int(year.group(1)) if year else datetime.datetime.now().year - 1

    DB.execute(
        "INSERT INTO evidence (client_id, path, cel, proof, year, confidence, tagged_at) "
        f"VALUES ('{client_id}', '{path}', '{cel}', '{level}', {year}, {confidence}, "
        f"'{datetime.datetime.now()}')"
    )
    DB.execute(f"UPDATE readiness SET status = 'READY' WHERE client_id = '{client_id}' AND cel = '{cel}'")
    DB.commit()
    print(f"tagged {filename} for {client_id}: {cel} {level} text={text[:200]!r}")
    return {"cel": cel, "proof": level, "confidence": confidence}


def amount(raw):
    return float(raw.replace("$", "").replace(",", ""))


def balances_match(prev_end, next_begin):
    return amount(prev_end) == amount(next_begin)


def is_expired(expiry_str):
    expiry = datetime.datetime.strptime(expiry_str, "%m/%d/%Y")
    return expiry < datetime.datetime.now()
