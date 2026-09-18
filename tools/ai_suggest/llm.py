"""Client voor het lokale OpenAI-compatibele endpoint (llama-server).

Netwerk is bewust ingeperkt: alleen loopback, geen proxy (ook niet via
http_proxy/https_proxy/all_proxy), geen redirects.
"""

import json
import math
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class LLMError(Exception):
    pass


class EndpointError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LLMError(f"redirect geweigerd ({code})")


def check_endpoint(url):
    """(basis-URL, poort) voor een lokaal http-endpoint, anders EndpointError."""
    parts = urlsplit(url)
    host = parts.hostname
    if (
        parts.scheme != "http"
        or host not in LOOPBACK_HOSTS
        or parts.username is not None
        or parts.password is not None
    ):
        raise EndpointError("endpoint moet lokaal zijn (127.0.0.1/::1/localhost)")
    try:
        port = parts.port or 80
    except ValueError:
        raise EndpointError("endpoint heeft een ongeldige poort")
    netloc = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    return f"http://{netloc}", port


def normalize_zekerheid(value):
    """(waarde in [0, 1], flags)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0, ["zekerheid ongeldig"]
    if math.isnan(v):
        return 0.0, ["zekerheid ongeldig"]
    if 1 < v <= 100:
        v = v / 100.0
    if v < 0 or v > 1:
        return min(max(v, 0.0), 1.0), ["zekerheid ongeldig"]
    return v, []


class LLMClient:
    def __init__(self, endpoint, model, api_key=None, timeout=300):
        self.base, self.port = check_endpoint(endpoint)
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def suggest(self, messages, schema, allowed):
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": messages,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "voorstel", "schema": schema},
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.base + "/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
        except LLMError:
            raise
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code}")
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            raise LLMError(f"endpoint onbereikbaar: {e}")

        try:
            content = json.loads(raw)["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("antwoord is geen geldige JSON")
        if not isinstance(data, dict):
            raise LLMError("antwoord is geen object")

        categorie = data.get("categorie")
        if categorie not in allowed:
            raise LLMError("categorie buiten de toegestane lijst")
        zoekterm = data.get("zoekterm")
        if not isinstance(zoekterm, str):
            raise LLMError("zoekterm ontbreekt")
        zekerheid, flags = normalize_zekerheid(data.get("zekerheid"))
        return {
            "categorie": categorie,
            "zoekterm": zoekterm,
            "zekerheid": zekerheid,
            "flags": flags,
        }
