"""Wolfram|Alpha Full Results API client (optional, needs an AppID)."""
import requests

API_URL = "https://api.wolframalpha.com/v2/query"


class WolframError(RuntimeError):
    pass


def query(text, app_id, timeout=10):
    """Return a list of (title, content) pods. Raises WolframError on failure."""
    if not app_id:
        raise WolframError("No Wolfram|Alpha AppID configured")
    try:
        r = requests.get(API_URL, params={"appid": app_id, "input": text, "output": "json"},
                         timeout=timeout)
        r.raise_for_status()
        data = r.json().get("queryresult", {})
    except requests.Timeout:
        raise WolframError("Wolfram|Alpha took too long to answer") from None
    except requests.ConnectionError:
        raise WolframError("No internet connection") from None
    except (requests.RequestException, ValueError) as exc:
        raise WolframError(f"Wolfram|Alpha request failed ({exc.__class__.__name__})") from None

    if data.get("error"):
        msg = data["error"].get("msg", "unknown error") if isinstance(data["error"], dict) else "unknown error"
        raise WolframError(f"Wolfram|Alpha error: {msg}")

    pods = []
    for p in data.get("pods", []):
        txt = [s["plaintext"] for s in p.get("subpods", []) if s.get("plaintext")]
        if txt:
            pods.append((p.get("title", ""), "\n".join(txt)))
    if pods:
        return pods

    hint = data.get("didyoumeans")
    if isinstance(hint, dict):
        hint = [hint]
    if hint:
        raise WolframError(f"No result. Did you mean: {hint[0].get('val')}?")
    raise WolframError("Wolfram|Alpha had no answer for that")
