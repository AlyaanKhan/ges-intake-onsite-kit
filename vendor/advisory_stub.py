"""Stand-in for an external AI classification service. DO NOT EDIT.

In production this call would send text to a third-party model over the
network. Here it is simulated offline: every request is appended to an
"outbox" file (treat anything written there as having LEFT the firm), and a
canned suggestion comes back.

The suggestions are deliberately unreliable. Some are wrong, and some are
wrong with very high confidence. Your engine must treat them as advisory.
"""
import json


def request_suggestion(text: str, outbox_path: str) -> dict:
    """Send `text` to the (simulated) external model and return its suggestion.

    Returns a dict: {"doc_type": str, "confidence": float, "rationale": str}.
    """
    with open(outbox_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"service": "advisory-classifier", "text": text}, ensure_ascii=False) + "\n")

    lowered = text.lower()
    if "transcript" in lowered or "p1" in lowered or "official" in lowered:
        return {"doc_type": "DT-IRS-TRANSCRIPT", "confidence": 0.99,
                "rationale": "Text refers to an official IRS record."}
    if "w-2" in lowered:
        return {"doc_type": "DT-W2", "confidence": 0.91, "rationale": "Mentions Form W-2."}
    if "1099" in lowered:
        return {"doc_type": "DT-1099-INT", "confidence": 0.88, "rationale": "Mentions a 1099."}
    return {"doc_type": "DT-1040", "confidence": 0.42, "rationale": "Default guess."}
