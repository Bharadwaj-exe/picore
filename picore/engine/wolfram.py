"""Wolfram|Alpha Full Results API client (optional; needs an AppID or the πCore proxy).

Everything that comes back is treated as untrusted: the structure is validated, the
size is bounded, and any surprise becomes a WolframError with a short message.
"""
import requests

API_URL = "https://api.wolframalpha.com/v2/query"
MAX_RESPONSE_BYTES = 2_000_000
MAX_POD_TEXT = 5_000
UNEXPECTED = "Unexpected response from Wolfram|Alpha"


class WolframError(RuntimeError):
    pass


def query(text, app_id=None, proxy_url=None, timeout=12):
    """Return a list of (title, content) pods. Raises WolframError on failure.

    With ``proxy_url`` the request goes to the πCore proxy (see proxy/), which adds
    the AppID server-side; otherwise Wolfram|Alpha is called directly with ``app_id``.
    """
    if proxy_url:
        url, params = proxy_url.rstrip("/") + "/query", {"input": text}
    elif app_id:
        url, params = API_URL, {"appid": app_id, "input": text, "output": "json"}
    else:
        raise WolframError("No Wolfram|Alpha AppID or proxy configured")
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 429:
            raise WolframError("Too many online questions right now. Try again in a minute")
        if proxy_url and r.status_code != 200:
            try:
                msg = r.json().get("error")
            except (ValueError, AttributeError):
                msg = None
            raise WolframError(str(msg)[:200] if msg else f"Proxy error {r.status_code}")
        r.raise_for_status()
        if len(r.content) > MAX_RESPONSE_BYTES:
            raise WolframError("Wolfram|Alpha sent an unexpectedly large response")
        body = r.json()
    except requests.Timeout:
        raise WolframError("Wolfram|Alpha took too long to answer") from None
    except requests.ConnectionError:
        raise WolframError("No internet connection") from None
    except (requests.RequestException, ValueError) as exc:
        raise WolframError(f"Wolfram|Alpha request failed ({exc.__class__.__name__})") from None

    data = body.get("queryresult") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise WolframError(UNEXPECTED)
    if data.get("error"):
        err = data["error"]
        msg = err.get("msg", "unknown error") if isinstance(err, dict) else "unknown error"
        raise WolframError(f"Wolfram|Alpha error: {str(msg)[:200]}")

    raw_pods = data.get("pods", [])
    if not isinstance(raw_pods, list):
        raise WolframError(UNEXPECTED)
    pods = []
    for p in raw_pods:
        if not isinstance(p, dict) or not isinstance(p.get("subpods", []), list):
            continue
        txt = [str(s["plaintext"]) for s in p.get("subpods", []) if isinstance(s, dict) and s.get("plaintext")]
        if txt:
            pods.append((str(p.get("title", ""))[:200], "\n".join(txt)[:MAX_POD_TEXT]))
    if pods:
        return pods

    hint = data.get("didyoumeans")
    if isinstance(hint, dict):
        hint = [hint]
    if isinstance(hint, list) and hint and isinstance(hint[0], dict) and hint[0].get("val"):
        raise WolframError(f"No result. Did you mean: {str(hint[0]['val'])[:100]}?")
    raise WolframError("Wolfram|Alpha had no answer for that")
