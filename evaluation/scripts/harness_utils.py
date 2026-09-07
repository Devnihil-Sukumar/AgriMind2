"""
==========================================================================
AgriMind Research Evaluation Harness

Shared utilities used by every run_*.py script:
  - safe JSON serialization (the pipeline embeds raw dataclasses)
  - per-run result persistence with checkpoint/resume
  - append-only progress logging
  - TRUSTAI / continuous-learning state backup + restore, so ablation
    studies don't contaminate the main trust-evolution trajectory
==========================================================================
"""

import dataclasses
import json
import os
import shutil
import signal
import sys
import time
import traceback


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt(f"received signal {signum}")


# A hard stop (SIGTERM, e.g. from an external "stop this task" request) does
# NOT normally trigger Python's `finally` blocks the way Ctrl-C
# (SIGINT/KeyboardInterrupt) does -- which twice left TRUSTAI's trust-state
# backup unrestored mid-ablation, contaminating the baseline trust-evolution
# trajectory until manually fixed. Converting SIGTERM into the same
# KeyboardInterrupt exception SIGINT already raises means every existing
# try/finally: restore_state(backups) block in run_agent_ablation.py and
# run_governance_ablation.py now fires on either kind of stop.
try:
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
except (ValueError, AttributeError, OSError):
    # SIGTERM handlers aren't installable on every platform/thread; the
    # scripts still clean up correctly on SIGINT/Ctrl-C either way.
    pass

# The UTF-8 stdout/stderr fix for Windows' cp1252 console (several
# app.* modules print Unicode glyphs at import time) now lives in
# app/__init__.py, which runs automatically the first time anything
# under app.* is imported below.

EVAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(EVAL_ROOT)
RAW_DIR = os.path.join(EVAL_ROOT, "data", "raw")
PROVIDER_DIR = os.path.join(EVAL_ROOT, "data", "provider_comparison")
ABLATION_DIR = os.path.join(EVAL_ROOT, "data", "ablation")
GOVERNANCE_DIR = os.path.join(EVAL_ROOT, "data", "governance_ablation")
LOG_PATH = os.path.join(EVAL_ROOT, "run_log.jsonl")

TRUST_STATE_PATH = os.path.join(
    PROJECT_ROOT, "app", "governance", "state", "trust_state.json"
)
LEARNING_STATE_PATH = os.path.join(
    PROJECT_ROOT, "app", "governance", "state", "crop_learning_state.json"
)

for _d in (RAW_DIR, PROVIDER_DIR, ABLATION_DIR, GOVERNANCE_DIR):
    os.makedirs(_d, exist_ok=True)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Several app modules (SQLite DB path, logs, .env) use paths relative
# to the project root. Force it regardless of the caller's CWD.
os.chdir(PROJECT_ROOT)


##########################################################################
# JSON safety
##########################################################################

def _default(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=_default, ensure_ascii=False)


def to_jsonable(obj):
    """Round-trip through the safe encoder to get a plain dict/list tree."""
    return json.loads(json.dumps(obj, default=_default, ensure_ascii=False))


##########################################################################
# Progress log (append-only, one JSON object per line)
##########################################################################

def log_event(event):
    event = dict(event)
    event["ts"] = time.time()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=_default) + "\n")
    print(f"[{event.get('phase','?')}] {event.get('run_id','')} "
          f"{event.get('status','')} {event.get('note','')}".strip())


##########################################################################
# Checkpoint helpers
##########################################################################

def result_path(directory, run_id):
    return os.path.join(directory, f"{run_id}.json")


def already_done(directory, run_id):
    """
    A run only counts as done if it actually succeeded. A saved
    result with `error` set (rate limit, timeout, etc.) is left as a
    record of what happened, but must NOT be treated as a completed
    checkpoint -- otherwise resuming after a failure would silently
    skip that run forever instead of retrying it.
    """

    path = result_path(directory, run_id)

    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    return record.get("error") is None


##########################################################################
# TRUSTAI / continuous-learning state backup + restore
#
# The main baseline matrix is meant to run in natural order so trust
# posteriors genuinely evolve across the session (that evolution is
# itself one of the metrics). Ablation studies intentionally perturb
# the same shared state files, so the harness snapshots them before an
# ablation phase and restores afterward -- otherwise ablation runs
# would leak into (and distort) the main trust trajectory.
##########################################################################

def backup_state():
    backups = {}
    for path in (TRUST_STATE_PATH, LEARNING_STATE_PATH):
        if os.path.exists(path):
            backup = path + ".bak"
            shutil.copy2(path, backup)
            backups[path] = backup
    return backups


def restore_state(backups):
    for path, backup in backups.items():
        if os.path.exists(backup):
            shutil.copy2(backup, path)
            os.remove(backup)


##########################################################################
# Timed, exception-safe execution of one pipeline run
##########################################################################

def run_pipeline(user_query, crop, latitude, longitude):
    """
    Calls the real dynamic_orchestrator end-to-end. Returns
    (result_dict_or_none, wall_time_seconds, error_str_or_none).
    """
    from app.orchestrator.dynamic_orchestrator import dynamic_orchestrator

    start = time.time()
    try:
        result = dynamic_orchestrator.run(
            user_query=user_query,
            crop=crop,
            latitude=latitude,
            longitude=longitude,
        )
        elapsed = time.time() - start
        return to_jsonable(result), elapsed, None
    except Exception as e:
        elapsed = time.time() - start
        return None, elapsed, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"


def run_and_save(directory, run_id, user_query, crop, latitude, longitude,
                  phase, extra_meta=None):
    """
    Skips cleanly if run_id already has a saved result (resumability).
    """
    if already_done(directory, run_id):
        log_event({"phase": phase, "run_id": run_id, "status": "skipped_cached"})
        return

    log_event({"phase": phase, "run_id": run_id, "status": "started",
                "note": f"crop={crop} query={user_query!r}"})

    result, elapsed, error = run_pipeline(user_query, crop, latitude, longitude)

    record = {
        "run_id": run_id,
        "phase": phase,
        "crop": crop,
        "query": user_query,
        "latitude": latitude,
        "longitude": longitude,
        "wall_time_seconds": round(elapsed, 3),
        "error": error,
        "meta": extra_meta or {},
        "result": result,
    }

    dump_json(record, result_path(directory, run_id))

    log_event({
        "phase": phase, "run_id": run_id,
        "status": "failed" if error else "completed",
        "note": f"{round(elapsed, 1)}s" + (f" ERROR: {error.splitlines()[0]}" if error else "")
    })
