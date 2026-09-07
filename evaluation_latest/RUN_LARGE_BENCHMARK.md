# Running the full 105-scenario benchmark on a second machine (Ollama only)

The benchmark dataset was expanded from 50 to **105 scenarios** to move
past the reviewer's N>=100 requirement: 2 new crops (apple, orange,
using AgriMind's own cached crop profiles paired with rice's real
sensor context at the same location -- see the `EXTRA_CROPS` docstring
in `evaluation_latest/dataset/build_dataset.py`), plus 5 new compound
(two-signal) scenario types per crop that test whether the executive
engine's decision priority order still resolves correctly when a
distractor signal is present.

Since every agent now runs on local Ollama (no Groq/Gemini quota
ceiling), this is a genuinely fresh run, not a resume -- do NOT copy
`evaluation_latest/results/` over from this laptop first. Every one of
the 105 x 4 = 420 (scenario, condition) pairs gets its own saved JSON
file in `evaluation_latest/results/raw/`; nothing is skipped or
overwritten across runs except a pair that has already succeeded.

---

## 1. Setup on the second laptop

```bash
git clone https://github.com/Devnihil-Sukumar/AgriMind2.git
cd AgriMind2
python -m venv venv
venv/Scripts/activate        # venv\Scripts\activate.bat on cmd.exe
pip install -r requirements.txt
```

Pull the Ollama model:

```bash
ollama pull qwen3:4b
```

Create `.env` in the project root and force every agent onto Ollama
(no API keys needed at all for the LLM-backed agents; `DATA_GOV_IN_API_KEY`
is still needed if Agmarknet live market data is used):

```
AGRIMIND_FORCE_PROVIDER=ollama
DATA_GOV_IN_API_KEY=your_key_here
```

Regenerate the dataset locally to confirm it matches (deterministic,
no LLM calls -- should print "Wrote 105 scenarios"):

```bash
python evaluation_latest/dataset/build_dataset.py
```

---

## 2. Run

The evaluator is checkpointed -- if it's interrupted (Ctrl-C, crash,
laptop sleep) just re-run the exact same command; it only retries
pairs that have not yet succeeded, nothing is repeated or overwritten.

**Full ablation, all 105 scenarios, all 4 conditions** (this is what
you want -- refreshes Tables 1/2/3/4 and every figure):

```bash
python evaluation_latest/evaluator.py
```

Progress streams live in the terminal and to
`evaluation_latest/results/run_log.jsonl`. With Ollama running locally
this will be CPU-bound rather than quota-bound -- expect it to take
hours depending on the machine, not days.

**Check progress at any time** (separate terminal):

```bash
dir evaluation_latest\results\raw
```

You should end up with up to 420 files there (105 scenarios x 4
conditions) once it finishes.

---

## 3. Package results to bring back

```bash
cd evaluation_latest
python -c "
import zipfile, os
paths = ['results/raw', 'results/run_log.jsonl']
with zipfile.ZipFile('n105_run_results.zip', 'w', zipfile.ZIP_DEFLATED) as z:
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

Bring `evaluation_latest/n105_run_results.zip` back to this laptop
(USB drive, cloud upload, or `git push` to a scratch branch on the
AgriMind2 repo -- results are just JSON, small either way).

---

## 4. Merge back on this laptop

Since this is a fresh Ollama-only run and the old results were mixed
Groq/Gemini/Ollama, decide whether to replace `results/raw/` entirely
(consistent single-provider run, recommended for a clean latency/quality
comparison) or merge alongside the old 11 (larger N, but a provider
confound). Tell me which when you bring the zip back and I'll do the
regeneration -- extracting into `results/raw/` and re-running
`compute_and_report.py`, then re-syncing every number quoted in the
manuscript against the new `aggregate_metrics.json`.
