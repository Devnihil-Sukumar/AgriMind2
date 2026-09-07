import sys

# Several modules under app.* print Unicode status glyphs (checkmarks,
# etc.) at import time. Windows' default console codepage (cp1252)
# can't encode those and crashes the process before anything runs.
# Fixed here, once, since this file runs before any app.* submodule
# regardless of which entrypoint imports it first (main.py, evaluation
# scripts, tests, ad-hoc scripts).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
