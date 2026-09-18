"""GPU-bewaking (0002-ai-suggest): geen eGPU, te weinig VRAM, spill."""

from .conftest import GIB, FakeHost


def test_no_egpu_exit_2_no_requests(sdb, stub, run, tmp_path):
    # AC8
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    no_egpu = FakeHost(tmp_path / "noegpu", stub.port, egpu=False)
    code, out, csv_path = run(host_=no_egpu)
    assert code == 2
    assert "eGPU niet aangesloten" in out
    assert len(stub.requests) == 0
    assert not csv_path.exists()


def test_card_vram_low_exit_3(sdb, stub, run, tmp_path):
    # AC9 (kaartniveau)
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    low = FakeHost(tmp_path / "low", stub.port, card_used=1 * GIB)
    code, out, csv_path = run(host_=low)
    assert code == 3
    assert "model draait niet op de eGPU" in out
    assert len(stub.requests) == 1


def test_model_process_vram_low_exit_3(sdb, stub, run, tmp_path):
    # AC9 (procesniveau): kaart vol door iets anders, model zelf niet op de eGPU
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    h = FakeHost(tmp_path / "other", stub.port, card_used=12 * GIB, model_vram=0)
    h.add_process("200", ["llama-server", "--alias", "gpt-oss-20b-MXFP4"], ppid="300", vram=11 * GIB, client_id="9")
    code, out, csv_path = run(host_=h)
    assert code == 3
    assert "model draait niet op de eGPU (0.0 GiB resident)" in out


def test_model_process_not_found_exit_3(sdb, stub, run, tmp_path):
    # N12: modelproces hangt onder een andere router (andere poort)
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    h = FakeHost(tmp_path / "wrongport", stub.port + 1 if stub.port < 65535 else stub.port - 1)
    code, out, csv_path = run(host_=h)
    assert code == 3
    assert f"model-proces niet gevonden op :{stub.port}" in out


def test_fdinfo_unreadable_exit_3(sdb, stub, run, tmp_path):
    # N12
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    h = FakeHost(tmp_path / "nofd", stub.port)
    import shutil

    shutil.rmtree(h.proc / "101" / "fdinfo")
    code, out, csv_path = run(host_=h)
    assert code == 3
    assert "fdinfo onleesbaar voor pid 101" in out


def test_duplicate_client_fds_counted_once(tmp_path):
    from tools.ai_suggest import gpu

    h = FakeHost(tmp_path, 6767, model_vram=6 * GIB)
    assert gpu.process_vram(str(h.proc), "101", "0000:03:00.0") == 6 * GIB


def test_connector_entries_ignored_and_igpu_skipped(tmp_path):
    from tools.ai_suggest import gpu

    h = FakeHost(tmp_path, 6767)
    egpu = gpu.find_egpu(str(h.sysfs))
    assert egpu["card"] == "card0"
    assert egpu["pdev"] == "0000:03:00.0"


def test_spill_warning_names_other_holder(sdb, stub, run, tmp_path):
    # Spill: model 6 GiB resident van 13 GiB bestand, Jan-desktop houdt 9 GiB vast
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    h = FakeHost(tmp_path / "spill", stub.port, card_used=15 * GIB,
                 model_vram=6 * GIB, model_file_size=13 * GIB)
    h.add_process("200", ["llama-server", "--alias", "gpt-oss-20b-MXFP4"], ppid="300", vram=9 * GIB, client_id="9")
    code, out, csv_path = run(host_=h)
    assert code == 0
    assert out.count("WAARSCHUWING: model past niet volledig op de eGPU") == 2  # voortgang + samenvatting
    assert "gpt-oss-20b-MXFP4" in out


def test_report_shows_vram(sdb, stub, run):
    sdb.add_tx("Test Bakker", "Brood", -4.5)
    code, out, csv_path = run()
    assert code == 0
    assert "model (pid 101) 12.0 GiB resident" in out
