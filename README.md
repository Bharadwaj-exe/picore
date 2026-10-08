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

### Mistake detective

Type your working as steps joined by `->`, and πCore finds the first wrong step:

```
check 2(x+3)=10 -> 2x+6=10 -> 2x=4 -> x=3     → step 4 is wrong (should be x = 2)
check x^2=4 -> x=2                             → lost the solution x = -2
check sqrt(x)=x-2 -> x=(x-2)^2                 → squaring added the extra root x = 1
check (a+b)^2 -> a^2+b^2                       → not equal (shows a counterexample)
```

Equations are compared by their solution sets, and expressions symbolically (with a numeric
counterexample when they differ). Final answers like `x=2 or x=3` are understood.

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

Or use a proxy instead of an AppID: `PICORE_WOLFRAM_PROXY` / `"wolfram_proxy_url"` (see [proxy/](proxy/README.md)).

Never commit the AppID. Before a public release, route Wolfram calls through a
small server you control so the key is not shipped inside the app.

## Build the Windows app

```bash
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File packaginguild.ps1
```

This runs the tests, builds `dist\PiCore\PiCore.exe`, checks that no API key file got bundled,
and self-tests the exe. If [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed
(`winget install JRSoftware.InnoSetup`), it also produces `dist\PiCore-Setup-<version>.exe`.

For a public release, deploy the proxy in [`proxy/`](proxy/README.md) and set `wolfram_proxy_url`,
so the AppID stays on the server.

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
    checker.py        mistake detective (step-by-step checking)
    wolfram.py        optional Wolfram|Alpha client (direct or via proxy)
  scenes/             loading, menu, calc, graph, history
  ui/                 theme + hand-drawn widgets
assets/               backgrounds, logo, music
tests/                pytest suite
packaging/            PyInstaller spec, Inno Setup script, build.ps1
proxy/                Cloudflare Worker that hides the Wolfram AppID
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
