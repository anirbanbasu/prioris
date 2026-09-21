import os
import socket
import subprocess
import time

import _mcp_server_lifecycle as lifecycle


def test_find_free_port_returns_bindable_port():
    port = lifecycle.find_free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((lifecycle.HOST, port))  # must not raise


def test_write_and_read_live_lock_roundtrip(tmp_path):
    lock_file = tmp_path / "mcp-server.lock"
    lifecycle.write_live_lock(lock_file, pid=os.getpid(), port=12345)
    entry = lifecycle.read_lock(lock_file)
    assert entry is not None
    assert entry["pid"] == os.getpid()
    assert entry["port"] == 12345


def test_read_lock_missing_file_returns_none(tmp_path):
    assert lifecycle.read_lock(tmp_path / "missing.lock") is None


def test_is_live_true_for_a_real_listening_socket():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind((lifecycle.HOST, 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert lifecycle.is_live(
            {"pid": os.getpid(), "port": port, "started_at": time.time()}
        )
    finally:
        srv.close()


def test_is_live_false_for_a_dead_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    assert (
        lifecycle.is_live({"pid": p.pid, "port": 1, "started_at": time.time()}) is False
    )


def test_try_claim_second_call_fails_while_first_claim_is_fresh(tmp_path):
    lock_file = tmp_path / "mcp-server.lock"
    assert lifecycle._try_claim(lock_file) is True
    assert lifecycle._try_claim(lock_file) is False


def test_try_claim_recovers_a_stale_placeholder(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "_CLAIM_STALE_SECONDS", 0.01)
    lock_file = tmp_path / "mcp-server.lock"
    assert lifecycle._try_claim(lock_file) is True
    time.sleep(0.05)
    assert lifecycle._try_claim(lock_file) is True


def test_remove_lock_missing_file_is_a_noop(tmp_path):
    lifecycle.remove_lock(tmp_path / "missing.lock")
