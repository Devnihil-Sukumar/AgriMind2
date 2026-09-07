# Running the full 50-scenario benchmark on a second machine

This laptop's Gemini free-tier quota (20 requests/day) and local Ollama
inference speed make a full sweep of the 50-scenario dataset
(`evaluation_latest/dataset/benchmark_queries.json`) impractical here --
at ~15-20 clean scenarios/day it would take several days per condition.
This runbook is for doing that run on a second, faster/idle machine,
then bringing the results back.

Only 11 of 50 scenarios have clean `full_system` results banked so far
(`evaluation_latest/results/raw/`). The other 39 -- plus the three
non-`full_system` ablation conditions needed to refresh Table 4 -- are
what this run is for.

---

## 1. Setup on the second laptop

```bash
git clone https://github.com/Devnihil-Sukumar/AgriMind2.git
cd AgriMind2
python -m venv venv
venv/Scripts/activate        # venv\Scripts\activate.bat on cmd.exe
pip install -r requirements.txt
```

Create `.env` in the project root (NOT committed to git -- copy your
keys over manually, do not paste them in chat):

```
GROQ_API_KEY=...
GEMINI_API_KEY=...
DATA_GOV_IN_API_KEY=...
```

If Ollama-backed agents are used (`app/agents/base_agent.py`
`FORCE_PROVIDER` / default provider routing), also install Ollama and
pull the model:

```bash
ollama pull qwen3:4b
```

---

## 2. Run

The evaluator is checkpointed -- interrupting and re-running only
retries pairs that have not yet succeeded, so it is safe to run in
chunks across multiple days if the second laptop also hits Gemini's
20/day ceiling.

**Headline metrics only** (fills in the 39 remaining `full_system`
scenarios -- this is what Tables 1/2/3 and Figures 1-4 read):

```bash
python evaluation_latest/evaluator.py --conditions full_system
```

**Full ablation** (also refreshes Table 4 -- ~4x the LLM calls, budget
several days of quota):

```bash
python evaluation_latest/evaluator.py
```

Progress streams to `evaluation_latest/results/run_log.jsonl` and
prints per-scenario status live. Re-run the same command to resume
after any interruption or quota exhaustion.

---

## 3. Package results to bring back

Once you've run as much as you want (even partial progress is useful --
more clean scenarios narrows the confidence intervals), zip only the
result artifacts, not the venv or the whole repo:

```bash
cd evaluation_latest
python -c "
import zipfile, os
paths = ['results/raw', 'results/run_log.jsonl']
with zipfile.ZipFile('n50_run_results.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    full = os.path.join(root, f)
                    z.write(full, os.path.relpath(full, '.'))
        elif os.path.isfile(p):
            z.write(p, p)
"
```

Bring `evaluation_latest/n50_run_results.zip` back to this laptop
(USB drive, cloud upload, or `git push` to a scratch branch on the
AgriMind2 repo -- your call, results are just JSON so they're small).

---

## 4. Merge back on this laptop

```bash
cd evaluation_latest
python -c "
import zipfile
zipfile.ZipFile('n50_run_results.zip').extractall('.')
"
```

This drops new files into `results/raw/` alongside the existing 11 --
it will NOT overwrite them since scenario IDs are unique filenames.
Then regenerate every table, figure, and `aggregate_metrics.json`:

```bash
cd ..
venv/Scripts/python.exe evaluation_latest/compute_and_report.py
```

Finally re-sync the manuscript's reported numbers by writing a fresh
`sync_numbers.py`-style diff script against the new
`aggregate_metrics.json` (the numbers will have moved again --
narrower confidence intervals, and the vegetation-clustering defect
found at N=11 should either persist or disappear at higher N, which is
itself a reportable finding either way).
