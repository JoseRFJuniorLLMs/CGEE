#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Painel de Integridade Orçamentária — backend leve para `painel.html`.

Serve o painel e expõe `/api/*` fazendo *proxy* ao HeraclitusDB via SDK gRPC.
Se o banco estiver offline, os endpoints devolvem 503 e o front-end cai
graciosamente no modo demonstração (dados sintéticos embutidos no HTML).

Sem dependências além do SDK `heraclitusdb` (opcional) — usa só a stdlib.

Uso:
    python painel_server.py            # http://127.0.0.1:8000
    PAINEL_PORT=9000 python painel_server.py
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ADDR = os.environ.get("HERACLITUS_ADDR", "127.0.0.1:7474")
PORT = int(os.environ.get("PAINEL_PORT", "8000"))

_db = None
_db_lock = threading.Lock()


def get_db():
    """Conecta (uma vez) ao HeraclitusDB. Devolve None se indisponível."""
    global _db
    with _db_lock:
        if _db is not None:
            return _db
        try:
            import heraclitusdb
            _db = heraclitusdb.connect(ADDR)
            print(f"[painel] conectado ao HeraclitusDB em {ADDR}")
            return _db
        except Exception as e:  # noqa: BLE001
            print(f"[painel] HeraclitusDB indisponivel ({ADDR}): {e}")
            return None


def _row_get(row, key, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _demojibake(s):
    """Repara texto UTF-8 que foi lido como latin1 (ex.: 'MinistÃ©rio' -> 'Ministerio')."""
    if isinstance(s, str) and ("Ã" in s or "Â" in s):
        try:
            return s.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def _parse_evento(row, idx):
    """Normaliza uma linha do banco no formato que o painel espera."""
    content = _row_get(row, "content", "{}")
    if isinstance(content, (bytes, bytearray)):
        content = content.decode("utf-8", "replace")
    if isinstance(content, str):
        content = _demojibake(content)
    lsn = _row_get(row, "lsn", idx)
    try:
        payload = json.loads(content) if isinstance(content, str) else (content or {})
    except Exception:  # noqa: BLE001
        payload = {}
    attrs = payload.get("attributes", payload) if isinstance(payload, dict) else {}
    return {
        "lsn": lsn,
        "data_oficial": attrs.get("data_oficial") or attrs.get("data"),
        "orgao": _demojibake(attrs.get("orgao", "")),
        "acao_orcamentaria": attrs.get("acao_orcamentaria", ""),
        "acao": _demojibake(attrs.get("acao", "")),
        "tipo_alteracao": _demojibake(attrs.get("tipo_alteracao", "Credito Suplementar")),
        "valor": attrs.get("valor", 0),
        "action_id": _demojibake(attrs.get("action_id", str(lsn))),
        "ano": attrs.get("ano"),
    }


def fetch_timeline(limit=2000):
    db = get_db()
    if db is None:
        return None
    rows = None
    for gql in (
        f"MATCH (n) WHERE n.lsn >= 0 RETURN n LIMIT {int(limit)}",
        f"MATCH (n) RETURN n LIMIT {int(limit)}",
    ):
        try:
            rows = db.query(gql)
            break
        except Exception as e:  # noqa: BLE001
            print(f"[painel] query falhou: {e}")
            rows = None
    if rows is None:
        try:
            rows = db.recall("orcamento credito portaria")
        except Exception:  # noqa: BLE001
            return None
    eventos = []
    for i, r in enumerate(rows or []):
        try:
            eventos.append(_parse_evento(r, i))
        except Exception:  # noqa: BLE001
            continue
    return eventos


def do_verify():
    db = get_db()
    if db is None:
        return None
    try:
        return bool(db.verify())
    except Exception as e:  # noqa: BLE001
        print(f"[painel] verify falhou: {e}")
        return None


def do_stats():
    db = get_db()
    if db is None:
        return None
    out = {"addr": ADDR}
    for m in ("stats", "get_stats"):
        f = getattr(db, m, None)
        if callable(f):
            try:
                out["stats"] = f()
                break
            except Exception:  # noqa: BLE001
                pass
    f = getattr(db, "collections", None)
    if callable(f):
        try:
            out["collections"] = f()
        except Exception:  # noqa: BLE001
            pass
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str))

    def log_message(self, *a):  # silencia o log padrão
        pass

    def do_GET(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        if p.path in ("/", "/index.html", "/painel.html"):
            try:
                with open(os.path.join(HERE, "painel.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:  # noqa: BLE001
                self._send(500, f"erro: {e}", "text/plain; charset=utf-8")
        elif p.path == "/api/stats":
            s = do_stats()
            self._json(503, {"online": False}) if s is None else self._json(200, {"online": True, **s})
        elif p.path == "/api/timeline":
            limit = int((q.get("limit", ["2000"])[0]))
            ev = fetch_timeline(limit)
            self._json(503, {"online": False}) if ev is None else self._json(200, {"online": True, "eventos": ev})
        elif p.path == "/api/verify":
            v = do_verify()
            self._json(503, {"online": False}) if v is None else self._json(200, {"integro": v})
        elif p.path == "/api/why":
            pid = q.get("portaria", [""])[0]
            ev = fetch_timeline(5000) or []
            hit = next((e for e in ev if str(e.get("action_id", "")).lower() == pid.lower()), None)
            self._json(404, {"encontrado": False}) if hit is None else self._json(200, {"encontrado": True, "evento": hit})
        else:
            self._json(404, {"erro": "rota desconhecida"})


def main():
    print("=" * 56)
    print(" Painel de Integridade Orcamentaria  -  HeraclitusDB")
    print("=" * 56)
    print(f" HeraclitusDB : {ADDR}  (cai em modo demo se offline)")
    print(f" Abra         : http://127.0.0.1:{PORT}/")
    print("=" * 56)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
