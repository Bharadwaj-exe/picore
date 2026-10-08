# πCore

A math solver with personality: type an expression, get step-friendly result
cards, graph it, and revisit everything in your history. It's styled gold on black, with
background music and loading messages like "Convincing π to Terminate".

## Run

```bash
pip install -r requirements.txt
python "Pi Core.py"
```

## What it can do (offline, via SymPy)

| Type this | You get |
|---|---|
| `2+2`, `5!`, `sqrt(8)`, `e^(i pi)` | exact result, decimal, prime factorization |
| `x^2 - 5x + 6` | factored/expanded form, derivative, roots |
| `2x + 3 = 7`, `x^2 = -1` | solutions (incl. complex) |
| `solve x+y=3 and x-y=1` | systems of equations |
| `d/dx sin(x)^2`, `derivative of x^3` | 1st and 2nd derivatives |
| `integrate x^2 from 0 to 3`, `integral of 1/x` | definite / indefinite integrals |
| `limit sin(x)/x as x->0` | limits |
| `factor …`, `expand …`, `simplify …` | that transformation |

Implicit multiplication (`2x`, `2(x+1)`, `sin x`) and symbols like `π √ ² ×` work.

**GRAPH** (Ctrl+G) plots any one-variable expression: scroll to zoom, drag to pan, hover to trace, R to reset.

**HISTORY** (Ctrl+H) lists past queries. Click a card to expand it, or click RUN to re-open it.
In the input box, ↑/↓ recalls previous inputs, Esc clears, and Ctrl+V pastes.

## Word questions (optional Wolfram|Alpha)

Anything SymPy can't parse (e.g. "distance to the moon") is sent to Wolfram|Alpha,
but only if an AppID is configured. Set it with any one of these:

1. Environment variable `PICORE_WOLFRAM_APPID`
2. `config.json` in the user data folder (`%APPDATA%\PiCore` on Windows): `{"wolfram_app_id": "…"}`
3. `picore.config.json` next to `Pi Core.py` (git-ignored, for development)

Never commit the AppID. Before a public release, route Wolfram calls through a
small server you control so the key is not shipped inside the app.

## Data

History is stored in SQLite at `<user data folder>/history.db`, and settings (music on/off) in
`config.json` in the same folder. No database server is needed.

## Project layout

```
Pi Core.py            entry point
picore/
  app.py              window, main loop, scene switching, music
  config.py, paths.py settings, asset & data-folder lookup (PyInstaller-safe)
  storage.py          SQLite history
  worker.py           background jobs so the UI never freezes
  engine/
    parser.py         safe parser (whitelisted AST -> SymPy, no eval)
    local.py          SymPy commands: solve, d/dx, integrate, limit, …
    wolfram.py        optional Wolfram|Alpha client
  scenes/             loading, menu, calc, graph, history
  ui/                 theme + hand-drawn widgets
assets/               backgrounds, logo, music
tests/                pytest suite
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
