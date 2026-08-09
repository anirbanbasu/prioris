"""Read/update .prioris/.review/schedule.json - quiz-me's spaced-repetition state.

This lives only here, never in a research_notes_update note's metadata:
NotesBackend's metadata is explicitly caller-owned, opaque, and NOT
filterable/searchable, but "every question ordered by how overdue it is,
across however many papers" is exactly the kind of query that can't be
done server-side over an opaque bag - see ../notes-model.md. Losing this
file resets real review progress, so unlike metadata_cache.py's cache it is
versioned, not gitignored.

Scheduling algorithm: a fixed geometric leveled scheme (not full SM-2 - its
easiness-factor tuning isn't justified at this scale). level 0 = 1 day
interval, doubling per level, capped at level 6 = 64 days. `correct`
increments level; `partial` leaves it unchanged (re-shown at the same
interval); `incorrect` resets it to 0. A note with no schedule entry has
never been asked and is always due, sorted before every already-scheduled
entry (treated as due at the Unix epoch).

Usage:
    uv run --project <plugin root> python shared/scripts/review_schedule.py record <note_id> <correct|partial|incorrect> [--asked-at ISO] [--root PATH]
    uv run --project <plugin root> python shared/scripts/review_schedule.py due <note_id> [<note_id> ...] [--now ISO] [--root PATH]
    uv run --project <plugin root> python shared/scripts/review_schedule.py prune <note_id> [--root PATH]

`record` updates (creating if absent) the note's schedule entry and prints
nothing on success. `due` prints a JSON array of the subset of the given
note ids that are currently due, most-overdue-first (never-asked ids first,
in the order given). `prune` prints "true"/"false" to stdout depending on
whether an entry existed to remove - used by the research_notes_delete
PostToolUse hook (../../hooks/hooks.json) so a deleted question's schedule
entry doesn't linger forever.
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_LEVEL_INTERVAL_DAYS = [1, 2, 4, 8, 16, 32, 64]
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_VALID_RESULTS = ("correct", "partial", "incorrect")


def interval_days(level: int) -> int:
    idx = min(level, len(_LEVEL_INTERVAL_DAYS) - 1)
    return _LEVEL_INTERVAL_DAYS[idx]


def schedule_path(root: Path) -> Path:
    return root / ".prioris" / ".review" / "schedule.json"


def load_schedule(root: Path) -> dict:
    path = schedule_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_schedule(root: Path, schedule: dict) -> None:
    path = schedule_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(schedule, indent=2, sort_keys=True))
    tmp.replace(path)


def record_result(root: Path, note_id: str, result: str, asked_at: str) -> dict:
    if result not in _VALID_RESULTS:
        raise ValueError(
            f"result must be one of correct/partial/incorrect, got {result!r}"
        )
    schedule = load_schedule(root)
    entry = schedule.get(note_id, {"level": 0, "times_asked": 0})
    entry["times_asked"] = entry.get("times_asked", 0) + 1
    if result == "correct":
        entry["level"] = entry.get("level", 0) + 1
    elif result == "incorrect":
        entry["level"] = 0
    entry["last_result"] = result
    entry["last_asked_at"] = asked_at
    schedule[note_id] = entry
    save_schedule(root, schedule)
    return entry


def prune(root: Path, note_id: str) -> bool:
    schedule = load_schedule(root)
    if note_id not in schedule:
        return False
    del schedule[note_id]
    save_schedule(root, schedule)
    return True


def _due_at(entry: dict | None) -> datetime:
    if entry is None:
        return _EPOCH
    last = datetime.fromisoformat(entry["last_asked_at"])
    return last + timedelta(days=interval_days(entry.get("level", 0)))


def due_order(note_ids: list[str], root: Path, now: datetime) -> list[str]:
    schedule = load_schedule(root)
    due = [note_id for note_id in note_ids if _due_at(schedule.get(note_id)) <= now]
    return sorted(due, key=lambda note_id: _due_at(schedule.get(note_id)))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    record_p = sub.add_parser("record")
    record_p.add_argument("note_id")
    record_p.add_argument("result")
    record_p.add_argument("--asked-at", default=None)
    record_p.add_argument("--root", default=".")

    due_p = sub.add_parser("due")
    due_p.add_argument("note_ids", nargs="+")
    due_p.add_argument("--now", default=None)
    due_p.add_argument("--root", default=".")

    prune_p = sub.add_parser("prune")
    prune_p.add_argument("note_id")
    prune_p.add_argument("--root", default=".")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.command == "record":
        asked_at = args.asked_at or datetime.now(UTC).isoformat()
        try:
            record_result(root, args.note_id, args.result, asked_at)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0

    if args.command == "due":
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(UTC)
        print(json.dumps(due_order(args.note_ids, root, now)))
        return 0

    removed = prune(root, args.note_id)
    print("true" if removed else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
