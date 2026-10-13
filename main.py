import base64
import hashlib
import json
import os
import random
import sys
import time
from urllib.request import Request, urlopen

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

SERVICE_NAME = os.environ.get("K_SERVICE", "demoshop")
REVISION = os.environ.get("K_REVISION", "local")
VERSION = os.environ.get("APP_VERSION", "v1")

PAYMENT_API_KEY_SECRET = os.environ.get("PAYMENT_API_KEY_SECRET", "")
PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY", "")

CHECKOUT_EXTRA_LATENCY_MS = float(os.environ.get("CHECKOUT_EXTRA_LATENCY_MS", "0"))
CHECKOUT_FAILURE_RATE = float(os.environ.get("CHECKOUT_FAILURE_RATE", "0"))

DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")

_METADATA_SA_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/email"
)
_SECRET_ACCESS_URL = "https://secretmanager.googleapis.com/v1/{version}:access"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "demo-not-for-production")


# ---------------------------------------------------------------------------
# structured logging
# ---------------------------------------------------------------------------

def log_json(severity, message, **fields):
    """Write one structured log line. ERROR+ goes to stderr, like Cloud Run expects."""
    entry = {
        "severity": severity,
        "message": message,
        "service": SERVICE_NAME,
        "revision": REVISION,
        "version": VERSION,
    }
    entry.update(fields)
    stream = sys.stderr if severity in ("ERROR", "CRITICAL") else sys.stdout
    print(json.dumps(entry), file=stream, flush=True)

def get_runtime_service_account():
    """Who is this application, from the container's own point of view."""
    try:
        req = Request(_METADATA_SA_URL, headers={"Metadata-Flavor": "Google"})
        with urlopen(req, timeout=0.5) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return os.environ.get("RUNTIME_SERVICE_ACCOUNT_LOCAL", "local-dev@example.com")


def _fetch_secret_value(secret_ref):
    """Fetch a Secret Manager payload over the REST API using the ambient credentials. """
    import google.auth
    import google.auth.transport.requests

    version = secret_ref if "/versions/" in secret_ref else secret_ref.rstrip("/") + "/versions/latest"
    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())

    resp = requests.get(
        _SECRET_ACCESS_URL.format(version=version),
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=2,
    )
    resp.raise_for_status()
    payload_b64 = resp.json()["payload"]["data"]
    return base64.b64decode(payload_b64).decode("utf-8")


def get_payment_credential():
    """Where did the payment credential come from, and is that acceptable?"""
    if PAYMENT_API_KEY_SECRET:
        try:
            value = _fetch_secret_value(PAYMENT_API_KEY_SECRET)
            fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
            return {"source": "secret-manager", "secure": True, "fingerprint": fingerprint}, value
        except Exception as exc:
            log_json(
                "ERROR",
                "Payment credential unavailable",
                runtime_service_account=get_runtime_service_account(),
                missing_role="roles/secretmanager.secretAccessor",
                detail=str(exc),
            )
            return {"source": "unavailable", "secure": False, "fingerprint": None}, None

    if PAYMENT_API_KEY:
        fingerprint = hashlib.sha256(PAYMENT_API_KEY.encode("utf-8")).hexdigest()[:12]
        return {"source": "environment", "secure": False, "fingerprint": fingerprint}, PAYMENT_API_KEY

    return {"source": "unavailable", "secure": False, "fingerprint": None}, None

def attempt_checkout(account_number, amount):
    """Run a (fake) payment. Latency and failure are entirely env-var driven,
    so `scripts/break_production.sh` can cause this exact incident without
    changing a line of code.
    """
    if CHECKOUT_EXTRA_LATENCY_MS > 0:
        time.sleep(CHECKOUT_EXTRA_LATENCY_MS / 1000.0)

    credential_info, credential_value = get_payment_credential()

    if credential_info["source"] == "unavailable":
        log_json(
            "ERROR",
            "Payment provider rejected the charge",
            reason="no_credential",
            account=account_number,
        )
        return False, "Payment provider rejected the charge", credential_info

    if random.random() < CHECKOUT_FAILURE_RATE:
        log_json(
            "ERROR",
            "Payment provider rejected the charge",
            reason="provider_declined",
            account=account_number,
            amount=amount,
        )
        return False, "Payment provider rejected the charge", credential_info

    log_json("INFO", "Checkout completed", account=account_number, amount=amount)
    return True, "Payment completed", credential_info

@app.route("/")
def root():
    return jsonify(status="ok", service=SERVICE_NAME, version=VERSION)

@app.route("/config")
def config():
    credential_info, _ = get_payment_credential()
    return jsonify(
        version=VERSION,
        runtime_service_account=get_runtime_service_account(),
        payment_credential=credential_info,
        checkout={
            "extra_latency_ms": CHECKOUT_EXTRA_LATENCY_MS,
            "failure_rate": CHECKOUT_FAILURE_RATE,
        },
    )

@app.route("/checkout")
def checkout_api():
    account = request.args.get("account", "demo-account")
    amount = request.args.get("amount", "10.00")
    ok, message, _ = attempt_checkout(account, amount)
    return jsonify(status="ok" if ok else "error", message=message), (200 if ok else 502)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == DEMO_USERNAME and password == DEMO_PASSWORD:
            session["user"] = username
            return redirect(url_for("pay"))
        error = "Invalid username or password."
    return render_template(
        "login.html",
        error=error,
        demo_username=DEMO_USERNAME,
        demo_password=DEMO_PASSWORD,
    )

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/pay", methods=["GET", "POST"])
def pay():
    if "user" not in session:
        return redirect(url_for("login"))

    result = None
    if request.method == "POST":
        account_number = request.form.get("account_number", "").strip()
        amount = request.form.get("amount", "").strip()
        ok, message, _ = attempt_checkout(account_number, amount)
        result = {"ok": ok, "message": message, "account_number": account_number, "amount": amount}

    return render_template("pay.html", user=session["user"], result=result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
