import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

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


def test_try_claim_is_refused_while_another_holder_has_the_flock(tmp_path):
    lock_file = tmp_path / "mcp-server.lock"
    fd = lifecycle.try_claim(lock_file)
    assert fd is not None
    try:
        # flock() treats separately-open()ed descriptors as independent holders, so this is
        # a genuine mutual-exclusion check even from within one process.
        assert lifecycle.try_claim(lock_file) is None
    finally:
        os.close(fd)
    again = lifecycle.try_claim(lock_file)
    assert (
        again is not None
    )  # released with the descriptor, no staleness timeout involved
    os.close(again)


_FLOCK_HOLDER = """
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
sys.stdout.write("held\\n")
sys.stdout.flush()
time.sleep(120)
"""


def test_try_claim_succeeds_once_the_flock_holder_is_sigkilled(tmp_path):
    """The kernel releases an flock when its holder dies, even under SIGKILL - which is why
    there is no stale-claim heuristic left to get wrong."""
    lock_file = tmp_path / "mcp-server.lock"
    claim = lifecycle.claim_path(lock_file)
    claim.parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(
        [sys.executable, "-c", _FLOCK_HOLDER, str(claim)], stdout=subprocess.PIPE
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline() == b"held\n"
        assert lifecycle.try_claim(lock_file) is None
        holder.kill()
        holder.wait(timeout=10)
        deadline = time.monotonic() + 5
        fd = None
        while fd is None and time.monotonic() < deadline:
            fd = lifecycle.try_claim(lock_file)
            if fd is None:
                time.sleep(0.05)
        assert fd is not None
        os.close(fd)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)


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
    # Simulate another process already spawning.
    claim_fd = lifecycle.try_claim(lock_file)
    assert claim_fd is not None

    def _spawn_then_release() -> None:
        try:
            lifecycle._spawn_server(lock_file, claim_fd)
        finally:
            os.close(claim_fd)

    threading.Thread(target=_spawn_then_release).start()
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


_SCRIPTS_DIR = Path(__file__).parent.parent / "shared" / "scripts"

_CONTENDER = """
import json, sys, time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import _mcp_server_lifecycle as lifecycle

start_at = float(sys.argv[3])
while time.time() < start_at:  # all contenders enter connect_or_spawn() together
    time.sleep(0.001)
host, port = lifecycle.connect_or_spawn(lock_file=Path(sys.argv[2]), timeout=90)
sys.stdout.write(json.dumps([host, port]))
"""


def _canonical_server_pids(lock_file: Path) -> set[int]:
    """Every live mcp_http_server.py process pointed at `lock_file`, via /proc (this sandbox
    has no ps/pgrep)."""
    found: set[int] = set()
    want = f"MCP_LIFECYCLE_LOCK_PATH={lock_file}".encode()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if b"mcp_http_server.py" not in (entry / "cmdline").read_bytes():
                continue
            if want not in (entry / "environ").read_bytes().split(b"\0"):
                continue
        except OSError:  # process exited between listdir and read
            continue
        found.add(int(entry.name))
    return found


def test_concurrent_connect_or_spawn_over_a_stale_lock_spawns_exactly_one_server(
    tmp_path,
):
    """The race the flock redesign exists to close.

    Pre-seed a *stale* info file (dead pid, dead port) - the exact leftover an uncleanly
    killed server leaves behind - then have N separate OS processes hit connect_or_spawn()
    simultaneously. The previous read-check-remove-recreate claim let several of them pass
    the staleness check before any of them acted on it, so several spawned, and the losers
    reproduced the `Could not set lock on file` Ladybug crash this whole plan fixes. A
    poller watches /proc throughout, so a second server that starts and then dies of that
    very crash is still caught.
    """
    lock_file = tmp_path / "mcp-server.lock"
    dead = subprocess.Popen([sys.executable, "-c", ""])
    dead.wait()
    # Written by hand rather than via write_live_lock() so started_at is genuinely old: a
    # lock left behind an hour ago is what an unclean shutdown actually leaves, and it is
    # the case where the old staleness heuristic let every racer through at once.
    lock_file.write_text(
        json.dumps(
            {
                "pid": dead.pid,
                "port": lifecycle.find_free_port(),
                "started_at": time.time() - 3600,
            }
        )
    )

    worker = tmp_path / "contender.py"
    worker.write_text(_CONTENDER)
    env = {
        **os.environ,
        "PRIORIS_MCP_STORAGE_DIR": str(tmp_path / "storage"),
        "PRIORIS_MCP_NOTES_DIR": str(tmp_path / "notes"),
        "PRIORIS_MCP_VECTOR_DIR": str(tmp_path / "vectors"),
        "PRIORIS_MCP_GRAPH_DIR": str(tmp_path / "graph"),
    }

    seen: set[int] = set()
    watching = True

    def _watch() -> None:
        while watching:
            seen.update(_canonical_server_pids(lock_file))
            time.sleep(0.01)

    watcher = threading.Thread(target=_watch)
    watcher.start()
    start_at = time.time() + 3.0
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(worker),
                str(_SCRIPTS_DIR),
                str(lock_file),
                str(start_at),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(6)
    ]
    try:
        results = []
        for proc in procs:
            out, err = proc.communicate(timeout=120)
            assert proc.returncode == 0, err.decode()
            results.append(json.loads(out))
        assert len({tuple(r) for r in results}) == 1, results
    finally:
        watching = False
        watcher.join()
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        entry = lifecycle.read_lock(lock_file)
        _kill(entry["pid"] if entry else None)

    assert len(seen) == 1, f"more than one canonical server was started: {seen}"
    assert not (log := lifecycle.log_path(lock_file)).exists() or (
        "Could not set lock on file" not in log.read_text()
    )


def test_spawned_server_is_reaped_rather_than_left_as_a_zombie(tmp_path, monkeypatch):
    """A discarded Popen leaves the canonical server as a zombie on exit, and a zombie still
    answers kill(pid, 0) - which made every "wait for it to die" poll here unable to ever
    succeed. connect_or_spawn()/_pid_alive() reap ours instead."""
    _isolate_data_dirs(monkeypatch, tmp_path)
    lock_file = tmp_path / "mcp-server.lock"
    _host, _port = lifecycle.connect_or_spawn(lock_file=lock_file, timeout=30)
    entry = lifecycle.read_lock(lock_file)
    assert entry is not None
    pid = entry["pid"]
    assert pid is not None

    os.kill(pid, 15)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and lifecycle._pid_alive(pid):
        time.sleep(0.05)
    assert not lifecycle._pid_alive(pid)
    assert _proc_state(pid) != "Z", "server was left as an unreaped zombie"


def test_pid_alive_treats_a_permission_error_as_alive(monkeypatch):
    """A pid owned by another user still answers kill(pid, 0) with EPERM, not ESRCH - that
    means it exists, just not ours to signal."""

    def _raise_permission_error(pid: int, sig: int) -> None:
        raise PermissionError

    monkeypatch.setattr(lifecycle.os, "kill", _raise_permission_error)
    assert lifecycle._pid_alive(12345) is True


def test_port_open_false_when_nothing_is_listening():
    assert lifecycle._port_open(lifecycle.find_free_port()) is False


def test_connect_or_spawn_times_out_while_the_claim_stays_held(tmp_path):
    lock_file = tmp_path / "mcp-server.lock"
    claim_fd = lifecycle.try_claim(lock_file)
    assert claim_fd is not None
    try:
        with pytest.raises(RuntimeError, match="did not become ready"):
            lifecycle.connect_or_spawn(lock_file=lock_file, timeout=0.1)
    finally:
        os.close(claim_fd)


def _proc_state(pid: int) -> str | None:
    """The process state letter from /proc/<pid>/stat, or None if the pid is gone."""
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text()
    except OSError:
        return None
    return stat[stat.rindex(")") + 2]
