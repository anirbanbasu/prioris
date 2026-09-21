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


import contextlib
import threading

import pytest


def _isolate_data_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    for var, sub in (
        ("PRIORIS_MCP_STORAGE_DIR", "storage"),
        ("PRIORIS_MCP_NOTES_DIR", "notes"),
        ("PRIORIS_MCP_VECTOR_DIR", "vectors"),
        ("PRIORIS_MCP_GRAPH_DIR", "graph"),
    ):
        monkeypatch.setenv(var, str(tmp_path / sub))


def _kill(pid: int | None) -> None:
    if pid is None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, 15)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and lifecycle._pid_alive(pid):
        time.sleep(0.1)


def test_connect_or_spawn_spawns_when_no_lock_present(tmp_path, monkeypatch):
    _isolate_data_dirs(monkeypatch, tmp_path)
    lock_file = tmp_path / "mcp-server.lock"
    try:
        host, port = lifecycle.connect_or_spawn(lock_file=lock_file)
        assert host == lifecycle.HOST
        entry = lifecycle.read_lock(lock_file)
        assert entry is not None
        assert entry["port"] == port
    finally:
        entry = lifecycle.read_lock(lock_file)
        _kill(entry["pid"] if entry else None)


def test_connect_or_spawn_reuses_live_server_without_spawning_twice(
    tmp_path, monkeypatch
):
    _isolate_data_dirs(monkeypatch, tmp_path)
    lock_file = tmp_path / "mcp-server.lock"
    try:
        first = lifecycle.connect_or_spawn(lock_file=lock_file)
        second = lifecycle.connect_or_spawn(lock_file=lock_file)
        assert first == second
    finally:
        entry = lifecycle.read_lock(lock_file)
        _kill(entry["pid"] if entry else None)


def test_connect_or_spawn_waits_on_an_in_flight_claim_instead_of_spawning(
    tmp_path, monkeypatch
):
    _isolate_data_dirs(monkeypatch, tmp_path)
    lock_file = tmp_path / "mcp-server.lock"
    assert (
        lifecycle._try_claim(lock_file) is True
    )  # simulate another process already spawning
    threading.Thread(target=lambda: lifecycle._spawn_server(lock_file)).start()
    try:
        host, port = lifecycle.connect_or_spawn(lock_file=lock_file, timeout=15)
        assert host == lifecycle.HOST
        assert isinstance(port, int)
    finally:
        entry = lifecycle.read_lock(lock_file)
        _kill(entry["pid"] if entry else None)


def test_client_reuses_the_same_canonical_server_across_calls():
    import anyio
    from _mcp_client import client

    async def _two_urls() -> tuple[str, str]:
        async with client() as c1:
            url1 = c1.transport.url
        async with client() as c2:
            url2 = c2.transport.url
        return url1, url2

    url1, url2 = anyio.run(_two_urls)
    assert url1 == url2
