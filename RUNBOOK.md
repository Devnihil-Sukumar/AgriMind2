# AgriMind — Run Book

AgriMind is a multi-agent, memory-augmented decision-intelligence system
for precision agriculture. This run book covers the AI recommendation
pipeline (Module 5A–5H): the FastAPI server that exposes it, and the
dashboard that talks to it.

---

## 1. What you're running

```
Browser (frontend/)  --->  FastAPI server (main.py)  --->  Dynamic Orchestrator
                                                              |
                                Crop Knowledge -> Data Collection -> Context
                                -> Planner -> Specialist Agents (Weather, Soil,
                                Satellite, Market, Historical) -> Collaborative
                                Reasoning -> Executive Decision -> Recommendation
                                -> Explainability -> TRUSTAI Governance
```

One HTTP call (`POST /api/recommend`) runs the entire pipeline and
returns the full result: specialist findings, reasoning, the executive
decision, the final recommendation, an explainability report, and the
TRUSTAI governance snapshot.

The dashboard (`frontend/`) is a static HTML/CSS/JS single-page app
served directly by the FastAPI server — no separate frontend build or
dev server is needed.

---

## 2. Prerequisites

| Requirement | Needed for | Notes |
|---|---|---|
| Python 3.11 + the `venv/` in this repo | Everything | `pip install -r requirements.txt` if you rebuild it |
| **Groq API key** | Planner, Market agent, Recommendation, Explanation | Set `GROQ_API_KEY` in `.env` |
| **Gemini API key** | Collaborative Reasoning | Set `GEMINI_API_KEY` in `.env` |
| **Ollama running locally**, with the `qwen3:4b` model pulled | Weather, Soil, Satellite, Historical agents | `ollama serve`, then `ollama pull qwen3:4b`. Default URL: `http://localhost:11434/api/chat` |
| **Google Earth Engine authentication** | Satellite imagery (Sentinel-2) | Run `earthengine authenticate` once. If this isn't set up, the SatelliteAgent degrades gracefully to `"unavailable"` — the pipeline still completes. |
| **ISRIC SoilGrids** | Live measured soil | **No API key needed.** `SOILGRIDS_URL` is already set. Rate-limited to ~5 req/min, so responses are cached in `data/soilgrids_cache.json`. SoilGrids masks built-up land, so some coordinates legitimately return no data and the soil stage falls back to `data/soil_data.csv`. Set `SOIL_LIVE_SOURCE=0` to force the synthetic dataset. |
| **data.gov.in API key** | Live Agmarknet mandi prices | Free key from https://data.gov.in (My Account → My Info). Set `DATA_GOV_IN_API_KEY` in `.env`. Without it — or when `api.data.gov.in` is unreachable — the market stage falls back to `data/market_prices.csv`. Set `MARKET_LIVE_SOURCE=0` to force the synthetic dataset. Note `AGMARKNET_URL` is the public website, not an API. |
| PostgreSQL | Only the legacy CRUD endpoints (`/farmers`, `/farms`, `/crops`, `/recommendations` DB routes) | **Not required** for the AI recommendation pipeline or the dashboard. |

All of the above are already configured in `.env` at the project root
(not committed to git). If a key is missing, that specific agent/stage
fails gracefully — TRUSTAI governance marks it `failed`/`unavailable`
and the pipeline still returns a result using whatever evidence it did
collect.

---

## 3. Starting the server

From the project root, with the virtual environment:

```bash
venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

(Add `--reload` while developing if you want auto-restart on file
changes.)

On startup you should see:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
[OK] Google Earth Engine initialized
✓ Gemini model: gemini-3.6-flash
```

Then open:

- **Dashboard:** http://localhost:8000/dashboard
- **API docs (Swagger UI):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/api/health

---

## 4. Using the dashboard

1. Open http://localhost:8000/dashboard
2. Fill in:
   - **Crop** — e.g. `rice`, `cotton`, `wheat`, `mango`. Free text; an
     unseen crop triggers on-the-fly crop-profile generation, which
     adds a few seconds.
   - **Question** — a natural-language farming question, e.g. *"What
     should I do to maximize cotton yield this season?"*
   - **Latitude / Longitude** — optional. Leave blank (or click **Use
     default location**) to fall back to the server default
     (`11.0168, 76.9558` — Coimbatore, India).
3. Click **Run Analysis**.

A single run makes 8+ sequential LLM calls (4 local Ollama specialist
agents + Groq planner/market/recommendation/explanation + Gemini
reasoning), plus live weather/satellite lookups. **Expect roughly
30 seconds to a few minutes**, depending on your local Ollama
throughput. The loading screen shows an elapsed-time counter so you
know it hasn't stalled.

Once it completes, results are organized into tabs:

- **Overview** — the headline recommendation, executive decision,
  estimated impact, farm context, recommended actions, and monitoring
  plan.
- **Specialists** — each agent's status, confidence, findings, and its
  individual TRUSTAI governance decision.
- **Reasoning & Governance** — collaborative reasoning summary and
  consensus, the TRUSTAI agent-trust table, and crop-level continuous
  learning state.
- **Explainability** — the causal decision trace, ranked evidence,
  known limitations, and the monitoring plan.
- **Raw JSON** — the full API response, for debugging.

---

## 5. Calling the API directly

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
        "query": "What should I do to maximize cotton yield?",
        "crop": "cotton"
      }'
```

`latitude` and `longitude` are optional — omit them (or pass `null`)
to use the server defaults. To override location:

```bash
curl -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
        "query": "Is it a good time to irrigate?",
        "crop": "rice",
        "latitude": 11.0168,
        "longitude": 76.9558
      }'
```

Other endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/recommend` | POST | Run the full multi-agent pipeline |
| `/api/defaults` | GET | Returns the server's default latitude/longitude/crop |
| `/api/health` | GET | Liveness check |

Full interactive schema (including the legacy CRUD routes) is at
`/docs`.

---

## 6. Troubleshooting

- **Server crashes on startup with `UnicodeEncodeError` /
  `'charmap' codec can't encode character`** — this was a Windows
  console-encoding issue (`gemini_client.py` and others print `✓`
  glyphs at import time, and Windows' default `cp1252` codepage can't
  encode them). `main.py` now reconfigures `stdout`/`stderr` to UTF-8
  at the top of the file, so this only resurfaces if that block is
  removed, or if you invoke a *different* entrypoint (a bare test
  script, `python -c "..."`, etc.) without the same fix.
- **Every specialist agent times out / fails** — Ollama likely isn't
  running. Start it with `ollama serve` and confirm
  `curl http://localhost:11434/api/tags` returns a model list
  including `qwen3:4b`.
- **`/api/recommend` returns HTTP 500** — check the server's console
  output; the error detail is also included in the JSON response
  body's `detail` field.
- **SatelliteAgent always shows `unavailable`** — Earth Engine
  credentials aren't set up. Run `earthengine authenticate`. The rest
  of the pipeline works fine without it.
- **Dashboard shows "Backend unreachable"** — the FastAPI server isn't
  running, or isn't reachable at the origin the dashboard was loaded
  from. Reload the page after starting the server.
- **Responses feel slow** — this is expected with local Ollama
  inference on CPU. Running the pytest suite (which also drives the
  pipeline) at the same time as the dashboard will make both slower
  since they compete for the same local model.

---

## 7. Running the test suite

```bash
venv/Scripts/python.exe -m pytest -q
```

Several tests exercise the live multi-agent pipeline end-to-end (same
LLM/API calls as a real dashboard request), so the full suite can take
several minutes.
