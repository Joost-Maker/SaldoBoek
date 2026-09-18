"""Fixtures voor AI suggest: synthetische DB, stub-LLM-server, nep-sysfs/proc.

Niets hier raakt echte bankdata, de echte GPU of het echte endpoint.
"""

import json
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

GIB = 1024 ** 3
MODEL = "Qwen3-14B-Q4_K_M"
EGPU_PDEV = "0000:03:00.0"

CATEGORIES = [
    ("Abonnementen", "uitgaven"),
    ("Boodschappen", "uitgaven"),
    ("Auto", "uitgaven"),
    ("Salaris", "inkomsten"),
    ("Ongecategoriseerd", "uitgaven"),
]


class SyntheticDB:
    """Een SaldoBoek-database met alleen fictieve data."""

    def __init__(self, tmp_path, users=("Test Gebruiker",)):
        from saldoboek.core.database import DatabaseManager

        self.path = tmp_path / "data" / "database.db"
        manager = DatabaseManager(db_path=self.path)
        for naam in users:
            manager.create_user(naam)
        with self.connect() as conn:
            # Geseede globale regels (o.a. 'da', 'ns') zouden synthetische tekst
            # eerst raken: elke test voegt zelf de regels toe die hij nodig heeft
            conn.execute("DELETE FROM categorisatie_regels")
            conn.execute("DELETE FROM categorieen")
            for (uid,) in conn.execute("SELECT id FROM gebruikers").fetchall():
                for naam, typ in CATEGORIES:
                    conn.execute(
                        "INSERT INTO categorieen (naam, type, beschrijving, gebruiker_id) VALUES (?, ?, '', ?)",
                        (naam, typ, uid),
                    )

    def connect(self):
        return sqlite3.connect(self.path)

    def add_tx(self, naam, omschrijving, bedrag, categorie="Ongecategoriseerd",
               datum="2026-09-17", gebruiker_id=1, rekening="NL00KNAB0000000000"):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO transacties (gebruiker_id, datum, rekening, tegenrekening, naam, "
                "omschrijving, bedrag, saldo_voor, valuta, categorie, rekeningtype) "
                "VALUES (?, ?, ?, 'NL00INGB0000000000', ?, ?, ?, 0, 'EUR', ?, 'betaalrekening')",
                (gebruiker_id, datum, rekening, naam, omschrijving, bedrag, categorie),
            )

    def add_rule(self, zoekterm, categorie, gebruiker_id=None):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO categorisatie_regels (zoekterm, categorie, gebruiker_id, actief) VALUES (?, ?, ?, 1)",
                (zoekterm, categorie, gebruiker_id),
            )


def default_responder(body):
    """Kiest de eerste toegestane categorie en de tegenpartij als zoekterm."""
    enum = body["response_format"]["json_schema"]["schema"]["properties"]["categorie"]["enum"]
    user = body["messages"][-1]["content"]
    naam = user.splitlines()[0].split(":", 1)[1].strip().lower()
    return 200, {"categorie": enum[0], "zoekterm": naam, "zekerheid": 0.9}


class StubLLM:
    """OpenAI-compatibele stub op 127.0.0.1 die verzoeken opslaat."""

    def __init__(self):
        self.requests = []
        self.responder = default_responder
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                stub.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                status, content = stub.responder(body)
                if status in (301, 302, 307):
                    self.send_response(status)
                    self.send_header("Location", content)
                    self.end_headers()
                    return
                if isinstance(content, dict):
                    content = json.dumps(content)
                payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class FakeHost:
    """Nep-/sys/class/drm en nep-/proc met een eGPU en een modelproces."""

    def __init__(self, tmp_path, port, card_used=12 * GIB, model_vram=12 * GIB,
                 model_file_size=1024, egpu=True):
        self.sysfs = tmp_path / "sys" / "class" / "drm"
        self.proc = tmp_path / "proc"
        devices = tmp_path / "sys" / "devices"
        self.sysfs.mkdir(parents=True)
        self.proc.mkdir(parents=True)

        # iGPU (klein) + connector-entry die de glob moet negeren
        igpu = devices / "0000:00:02.0"
        igpu.mkdir(parents=True)
        (igpu / "mem_info_vram_total").write_text(str(512 * 1024 ** 2))
        (self.sysfs / "card1").mkdir()
        os.symlink(igpu, self.sysfs / "card1" / "device")
        (self.sysfs / "card0-DP-5").mkdir()

        self.egpu_dir = devices / EGPU_PDEV
        if egpu:
            self.egpu_dir.mkdir(parents=True)
            (self.egpu_dir / "mem_info_vram_total").write_text(str(16 * GIB))
            (self.egpu_dir / "mem_info_vram_used").write_text(str(card_used))
            (self.sysfs / "card0").mkdir()
            os.symlink(self.egpu_dir, self.sysfs / "card0" / "device")

        self.model_file = tmp_path / "model.gguf"
        with open(self.model_file, "wb") as f:
            f.truncate(model_file_size)

        self.add_process("100", ["llama-server", "--port", str(port)], ppid="1")
        self.add_process(
            "101",
            ["llama-server", "--alias", MODEL, "--model", str(self.model_file), "--device", "Vulkan1"],
            ppid="100",
            vram=model_vram,
        )

    def add_process(self, pid, args, ppid="1", vram=None, pdev=EGPU_PDEV, client_id="7"):
        d = self.proc / pid
        (d / "fdinfo").mkdir(parents=True)
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in args) + b"\0")
        (d / "status").write_text(f"Name:\tx\nPPid:\t{ppid}\n")
        if vram is not None:
            (d / "fdinfo" / "5").write_text(
                f"pos:\t0\ndrm-driver:\tamdgpu\ndrm-pdev:\t{pdev}\n"
                f"drm-client-id:\t{client_id}\ndrm-memory-vram:\t{vram // 1024} KiB\n"
            )
            # zelfde client via tweede fd: mag niet dubbel tellen
            (d / "fdinfo" / "6").write_text(
                f"drm-pdev:\t{pdev}\ndrm-client-id:\t{client_id}\ndrm-memory-vram:\t{vram // 1024} KiB\n"
            )

    def set_card_used(self, value):
        (self.egpu_dir / "mem_info_vram_used").write_text(str(value))


@pytest.fixture
def stub():
    s = StubLLM()
    yield s
    s.close()


@pytest.fixture
def sdb(tmp_path):
    return SyntheticDB(tmp_path)


@pytest.fixture
def host(tmp_path, stub):
    return FakeHost(tmp_path, stub.port)


@pytest.fixture
def run(sdb, stub, host, tmp_path, capsys, monkeypatch):
    """Draai de CLI tegen de synthetische omgeving; geeft (exitcode, stdout, csvpad)."""
    from tools.ai_suggest.__main__ import main

    monkeypatch.delenv("AI_SUGGEST_API_KEY", raising=False)

    def _run(*extra, db=None, host_=None, endpoint=None):
        h = host_ or host
        out = tmp_path / "review.csv"
        capsys.readouterr()  # DatabaseManager-output van de opbouw weggooien
        args = [
            "--db", str(db or sdb.path),
            "--out", str(out),
            "--endpoint", endpoint or stub.url,
            "--sysfs-root", str(h.sysfs),
            "--proc-root", str(h.proc),
            *extra,
        ]
        code = main(args)
        return code, capsys.readouterr().out, out

    return _run


def read_review(path):
    import csv

    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    return rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]
