"""CLI-randen, alleen-lezen DB, review-CSV en prompt (0002-ai-suggest)."""

import hashlib
import sqlite3

import pytest

from tools.ai_suggest.db import ReadOnlyDB
from tools.ai_suggest.prompt import fewshot_examples
from tools.ai_suggest.review import COLUMNS

from .conftest import SyntheticDB, read_review


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- read-only (AC10) ---

def test_db_hash_unchanged(sdb, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    sdb.add_tx("Test Garage", "APK", -60.0, categorie="Auto")
    before = sha256(sdb.path)
    code, out, csv_path = run()
    assert code == 0
    assert sha256(sdb.path) == before


def test_connection_is_readonly(sdb):
    db = ReadOnlyDB(sdb.path)
    with pytest.raises(sqlite3.OperationalError):
        db.conn.execute("DELETE FROM transacties")
    db.close()


# --- review-CSV (AC11) ---

def test_header_and_empty_akkoord(sdb, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    sdb.add_tx("Test Werkgever", "Salaris", 2500.0)
    code, out, csv_path = run()
    header, rows = read_review(csv_path)
    assert header == COLUMNS
    assert "sleutel" in header
    assert all(r["akkoord"] == "" for r in rows)
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not csv_path.with_name(csv_path.name + ".tmp").exists()


def test_default_output_next_to_db(sdb, stub, host, capsys, monkeypatch):
    from tools.ai_suggest.__main__ import main

    sdb.add_tx("Test Bakker", "Brood", -4.5)
    capsys.readouterr()
    code = main(["--db", str(sdb.path), "--endpoint", stub.url,
                 "--sysfs-root", str(host.sysfs), "--proc-root", str(host.proc)])
    assert code == 0
    files = list(sdb.path.parent.glob("ai_review_*.csv"))
    assert len(files) == 1


# --- CLI ---

def test_non_loopback_endpoint_refused(sdb, stub, run, monkeypatch):
    # R1: exit != 0, stub krijgt niets, DB wordt niet eens geopend
    opened = []
    monkeypatch.setattr("tools.ai_suggest.__main__.ReadOnlyDB", lambda p: opened.append(p))
    code, out, csv_path = run(endpoint="http://example.com:6767")
    assert code != 0
    assert "endpoint moet lokaal zijn" in out
    assert len(stub.requests) == 0
    assert opened == []


def test_single_user_default(sdb, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    code, out, csv_path = run()
    assert code == 0


def test_multiple_users_requires_flag(tmp_path, stub, host, run):
    db2 = SyntheticDB(tmp_path / "twee", users=("Test Een", "Test Twee"))
    db2.add_tx("Test Bakker", "Brood", -4.5, gebruiker_id=2)
    code, out, csv_path = run(db=db2.path)
    assert code == 1
    assert "--gebruiker" in out and "Test Een" in out
    assert len(stub.requests) == 0
    code, out, csv_path = run("--gebruiker", "2", db=db2.path)
    assert code == 0
    assert len(stub.requests) == 1


def test_missing_db(tmp_path, run):
    code, out, csv_path = run(db=tmp_path / "bestaat-niet.db")
    assert code == 1
    assert "niet gevonden" in out


# --- prompt / few-shot ---

def test_fewshot_limit_and_order(sdb):
    for i in range(20):
        sdb.add_tx(f"Test Winkel {i:02d}", "x", -1.0, categorie="Boodschappen", datum=f"2026-08-{i + 1:02d}")
    sdb.add_tx("Test Winkel 19", "dubbel", -1.0, categorie="Boodschappen", datum="2026-07-01")
    sdb.add_tx("Test Open", "x", -1.0)  # ongecategoriseerd: nooit als voorbeeld
    db = ReadOnlyDB(sdb.path)
    examples = fewshot_examples(db.transactions(1))
    db.close()
    assert len(examples) == 15
    assert examples[0]["naam"] == "Test Winkel 19"
    assert len({e["naam"] for e in examples}) == 15
    assert all(e["categorie"] != "Ongecategoriseerd" for e in examples)
