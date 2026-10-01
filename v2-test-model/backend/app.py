import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import pandas as pd
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from model.research_features import FEATURE_ORDER, extract_url_features

RESEARCH_MODEL_DIR = ROOT_DIR / "model" / "research"
URL_MODEL_NAME = "phiusiil_no_https_rf.pkl"
TEXT_MODEL_NAME = "sms_spam_word_char_logreg.pkl"
MAX_TEXT_LENGTH = 5_000
MAX_REQUEST_BYTES = 64 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
FRONTEND_ORIGIN = "http://127.0.0.1:5500"


def load_model_artifact(filename, expected_feature_count=None):
    path = RESEARCH_MODEL_DIR / filename
    try:
        loaded_model = joblib.load(path)
        classes = set(loaded_model.classes_)
        if not {0, 1}.issubset(classes):
            raise ValueError("expected a binary model with classes 0 and 1")
        if not callable(getattr(loaded_model, "predict_proba", None)):
            raise ValueError("model does not provide predict_proba")
        if (
            expected_feature_count is not None
            and loaded_model.n_features_in_ != expected_feature_count
        ):
            raise ValueError(
                f"expected {expected_feature_count} features, "
                f"found {loaded_model.n_features_in_}"
            )
        return loaded_model
    except Exception:
        app.logger.exception("Could not load model artifact %s", filename)
        return None


url_model = load_model_artifact(URL_MODEL_NAME, len(FEATURE_ORDER))
text_model = load_model_artifact(TEXT_MODEL_NAME)

URL_PATTERN = re.compile(
    r"""(?i)\b(?:https?://|www\.)[^\s<>'"]+"""
    r"""|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>'"]*)?"""
)

LOOKALIKE_PATTERNS = ("arnaz0n", "paypa1", "g00gle")
URGENCY_PHRASES = (
    "urgent",
    "act now",
    "verify immediately",
    "account suspended",
)


@app.after_request
def add_cors_headers(response):
    if request.headers.get("Origin") == FRONTEND_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = FRONTEND_ORIGIN
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def error_response(code, explanation, status):
    return jsonify({"error": code, "explanation": explanation}), status


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return error_response(
        "request_too_large",
        f"Request body is too large. Keep it under {MAX_REQUEST_BYTES // 1024} KB.",
        413,
    )


@app.errorhandler(500)
def internal_server_error(_error):
    return error_response(
        "internal_error",
        "The local checker could not complete this request. Check the backend terminal for details.",
        500,
    )


@app.errorhandler(404)
def endpoint_not_found(_error):
    return error_response(
        "not_found",
        "Endpoint not found. This V2 backend supports POST /check and GET /health.",
        404,
    )


def validate_check_request():
    if not request.is_json:
        return None, error_response(
            "unsupported_media_type",
            "Send a JSON request with Content-Type: application/json.",
            415,
        )

    try:
        data = request.get_json()
    except BadRequest:
        return None, error_response(
            "invalid_json", "Request body must contain valid JSON.", 400
        )

    if not isinstance(data, dict):
        return None, error_response(
            "invalid_json_shape",
            "Request body must be a JSON object with a text field.",
            400,
        )

    if "text" not in data:
        return None, error_response(
            "missing_text", "Request JSON is missing the required text field.", 400
        )

    text = data["text"]
    if not isinstance(text, str):
        return None, error_response(
            "invalid_text_type", "The text field must be a string.", 400
        )
    if not text.strip():
        return None, error_response(
            "empty_text", "The text field must not be empty.", 400
        )
    if len(text) > MAX_TEXT_LENGTH:
        return None, error_response(
            "text_too_long",
            f"Text is too long. Maximum length is {MAX_TEXT_LENGTH} characters.",
            413,
        )

    return text, None


def check_urgency(text):
    lowered = text.lower()
    return any(phrase in lowered for phrase in URGENCY_PHRASES)


def check_lookalike_domain(text):
    lowered = text.lower()
    return any(pattern in lowered for pattern in LOOKALIKE_PATTERNS)


def find_first_url(text):
    """Return the first parseable URL candidate, skipping malformed candidates."""
    malformed_candidate_found = False

    for match in URL_PATTERN.finditer(text):
        candidate = match.group(0).rstrip(".,!?;:)]}")
        parsed_candidate = candidate if "://" in candidate else f"//{candidate}"

        try:
            parsed = urlsplit(parsed_candidate)
            hostname = parsed.hostname
            # Accessing .port validates malformed and out-of-range ports.
            parsed.port
        except (ValueError, UnicodeError):
            malformed_candidate_found = True
            continue

        if not hostname or parsed.scheme.lower() not in {"", "http", "https"}:
            malformed_candidate_found = True
            continue

        return candidate, malformed_candidate_found

    return None, malformed_candidate_found


def simple_explanation(signals, risk_level, url_score_available):
    if signals:
        signal_text = ", ".join(signals)
        opening = f"This message has a {risk_level} risk rating. Warning signals: {signal_text}."
    else:
        opening = (
            f"This message has a {risk_level} risk rating. "
            "No obvious warning signals were detected."
        )

    url_status = (
        "A valid URL string was scored."
        if url_score_available
        else "No valid URL string was scored."
    )
    return (
        f"{opening} {url_status} The URL model scores URL-string patterns only; "
        "it does not open or inspect the website. The text model is for English "
        "SMS spam-vs-ham only. Neither model proves that something is safe or fraudulent."
    )


def make_result(text):
    if url_model is None or text_model is None:
        return None

    signals = []
    rule_risks = []

    if check_urgency(text):
        signals.append("Urgency language detected")
        rule_risks.append(0.45)

    if check_lookalike_domain(text):
        signals.append("Lookalike domain text detected")
        rule_risks.append(0.60)

    rule_risk = 1.0
    for risk in rule_risks:
        rule_risk *= 1.0 - risk
    rule_risk = 1.0 - rule_risk

    url, malformed_url_found = find_first_url(text)
    url_phishing_score = None
    if url:
        try:
            url_features = extract_url_features(url)
        except (ValueError, UnicodeError):
            malformed_url_found = True
        else:
            features = pd.DataFrame([url_features], columns=FEATURE_ORDER)
            probabilities = url_model.predict_proba(features)[0]
            phishing_index = list(url_model.classes_).index(1)
            url_phishing_score = float(probabilities[phishing_index])

        if url_phishing_score is not None and url_phishing_score >= 0.50:
            signals.append("URL model found phishing-like URL patterns")

    if malformed_url_found and url_phishing_score is None:
        signals.append("Malformed URL string skipped by URL model")

    text_probabilities = text_model.predict_proba([text])[0]
    spam_index = list(text_model.classes_).index(1)
    message_spam_score = float(text_probabilities[spam_index])
    if message_spam_score >= 0.50:
        signals.append("Text model found English SMS spam-like wording")

    # These are separate experimental scores, not calibrated fraud probabilities.
    component_scores = {
        "rule_warnings": {
            "score": round(rule_risk * 100),
            "scope": "Selected urgency and lookalike-string rules only",
        },
        "url_phishing": {
            "score": (
                round(url_phishing_score * 100)
                if url_phishing_score is not None
                else None
            ),
            "scope": "URL-string patterns only; no live URL inspection",
        },
        "message_spam": {
            "score": round(message_spam_score * 100),
            "scope": "English SMS spam-vs-ham only",
        },
    }
    available_scores = [
        component["score"]
        for component in component_scores.values()
        if component["score"] is not None
    ]
    risk_score = max(0, min(100, max(available_scores)))

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    score_note = (
        "risk_score is the largest of the rule, URL, and text component scores; "
        "risk_level is high at 70–100, medium at 40–69, and low below 40. "
        "The URL model scores URL-string patterns only and never opens a link. "
        "The text model is for English SMS spam-vs-ham only. Neither model proves "
        "safety or fraud, and these values are not calibrated probabilities."
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "signals": signals,
        "explanation": simple_explanation(
            signals, risk_level, url_phishing_score is not None
        ),
        "component_scores": component_scores,
        "score_note": score_note,
    }


@app.get("/health")
def health():
    models = {
        "url_phishing": {
            "loaded": url_model is not None,
            "artifact": URL_MODEL_NAME,
        },
        "message_spam": {
            "loaded": text_model is not None,
            "artifact": TEXT_MODEL_NAME,
        },
    }
    healthy = all(model["loaded"] for model in models.values())
    return jsonify({"status": "ok" if healthy else "degraded", "models": models}), (
        200 if healthy else 503
    )


@app.post("/check")
def check():
    text, error = validate_check_request()
    if error:
        return error

    result = make_result(text)
    if result is None:
        return error_response(
            "model_unavailable",
            "One or more local model artifacts did not load. Check GET /health.",
            503,
        )
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
