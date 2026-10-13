import hashlib
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def app_module(monkeypatch):
    """Reload main.py with a clean, known environment for every test."""
    for var in (
        "PAYMENT_API_KEY_SECRET",
        "PAYMENT_API_KEY",
        "CHECKOUT_EXTRA_LATENCY_MS",
        "CHECKOUT_FAILURE_RATE",
        "APP_VERSION",
        "K_REVISION",
    ):
        monkeypatch.delenv(var, raising=False)

    import main as module

    importlib.reload(module)
    return module


@pytest.fixture
def client(app_module):
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


# ---------------------------------------------------------------------------
# /
# ---------------------------------------------------------------------------

def test_root_reports_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "demoshop"


# ---------------------------------------------------------------------------
# /config -- credential source reporting
# ---------------------------------------------------------------------------

def test_config_unavailable_when_no_credential_configured(client):
    resp = client.get("/config")
    body = resp.get_json()
    assert body["payment_credential"] == {"source": "unavailable", "secure": False, "fingerprint": None}


def test_config_reports_environment_source(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    resp = client.get("/config")
    body = resp.get_json()

    expected_fp = hashlib.sha256(b"pk_live_demoshop").hexdigest()[:12]
    assert body["payment_credential"] == {
        "source": "environment",
        "secure": False,
        "fingerprint": expected_fp,
    }


def test_config_reports_secret_manager_source(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY_SECRET", "projects/demo/secrets/payment-api-key")
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "_fetch_secret_value", lambda ref: "pk_live_demoshop")
    client = app_module.app.test_client()

    resp = client.get("/config")
    body = resp.get_json()

    expected_fp = hashlib.sha256(b"pk_live_demoshop").hexdigest()[:12]
    assert body["payment_credential"] == {
        "source": "secret-manager",
        "secure": True,
        "fingerprint": expected_fp,
    }


def test_config_reports_unavailable_when_secret_fetch_fails(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY_SECRET", "projects/demo/secrets/payment-api-key")
    importlib.reload(app_module)

    def boom(_ref):
        raise RuntimeError("permission denied")

    monkeypatch.setattr(app_module, "_fetch_secret_value", boom)
    client = app_module.app.test_client()

    resp = client.get("/config")
    body = resp.get_json()
    assert body["payment_credential"]["source"] == "unavailable"
    assert body["payment_credential"]["secure"] is False


def test_config_never_exposes_the_secret_value(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    resp = client.get("/config")
    assert "pk_live_demoshop" not in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# /checkout -- the incident-drill lever
# ---------------------------------------------------------------------------

def test_checkout_succeeds_by_default_with_a_credential(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    resp = client.get("/checkout")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_checkout_fails_without_any_credential(client):
    resp = client.get("/checkout")
    assert resp.status_code == 502
    assert resp.get_json()["status"] == "error"


def test_checkout_respects_injected_latency(app_module, monkeypatch):
    import time

    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    monkeypatch.setenv("CHECKOUT_EXTRA_LATENCY_MS", "50")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    start = time.monotonic()
    client.get("/checkout")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05


def test_checkout_respects_injected_failure_rate(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    monkeypatch.setenv("CHECKOUT_FAILURE_RATE", "1.0")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    resp = client.get("/checkout")
    assert resp.status_code == 502


def test_checkout_failure_logs_structured_error(app_module, monkeypatch, capsys):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    monkeypatch.setenv("CHECKOUT_FAILURE_RATE", "1.0")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    client.get("/checkout")
    captured = capsys.readouterr()
    assert "Payment provider rejected the charge" in captured.err
    assert '"severity": "ERROR"' in captured.err


# ---------------------------------------------------------------------------
# human-facing login + pay flow
# ---------------------------------------------------------------------------

def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Sign in" in resp.data


def test_login_rejects_wrong_credentials(client):
    resp = client.post("/login", data={"username": "demo", "password": "wrong"})
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data


def test_login_accepts_demo_credentials_and_redirects_to_pay(client):
    resp = client.post(
        "/login",
        data={"username": "demo", "password": "demo1234"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/pay")


def test_pay_page_requires_login(client):
    resp = client.get("/pay", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_pay_page_submits_a_dummy_payment_once_logged_in(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    client.post("/login", data={"username": "demo", "password": "demo1234"})
    resp = client.post("/pay", data={"account_number": "0123456789", "amount": "25.00"})

    assert resp.status_code == 200
    assert b"Payment completed" in resp.data
    assert b"0123456789" in resp.data


def test_logout_clears_session(app_module, monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "pk_live_demoshop")
    importlib.reload(app_module)
    client = app_module.app.test_client()

    client.post("/login", data={"username": "demo", "password": "demo1234"})
    client.get("/logout")
    resp = client.get("/pay", follow_redirects=False)
    assert resp.status_code == 302
