#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ingestao de AMOSTRA real do SIOP no HeraclitusDB para o painel AO VIVO.

Le o CSV de Alteracoes Orcamentarias (colunas reais do SIOP), limpa e faz
append cronologico (o "leito do rio" append-only). Corrige o mapeamento de
valor que o main.py erra: usa val_acrescimo / val_reducao (e nao tipo_credito).

Env:
  HERACLITUS_ADDR  (default 127.0.0.1:7474)
  CSV              (default alteracoesorcamentarias_2026.csv)
  CAP              (default 6000 linhas; 0 = todas)
"""
import csv
import datetime
import json
import os

import heraclitusdb

HERE = os.path.dirname(os.path.abspath(__file__))
ADDR = os.environ.get("HERACLITUS_ADDR", "127.0.0.1:7474")
CSV = os.environ.get("CSV", os.path.join(HERE, "alteracoesorcamentarias_2026.csv"))
CAP = int(os.environ.get("CAP", "6000"))


def br_float(s):
    s = (s or "").strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not s:
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_data(s):
    s = (s or "").strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def nome(s):
    """ '53000 - Ministerio...' -> 'Ministerio...' """
    s = (s or "").strip()
    return s.split(" - ", 1)[1] if " - " in s else s


def main():
    print(f"Conectando a {ADDR} ...")
    db = heraclitusdb.connect(ADDR)

    rows = []
    with open(CSV, encoding="latin1", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            d = parse_data(row.get("data_publicacao_instrumento_legal"))
            if not d:
                continue
            valor = br_float(row.get("val_acrescimo")) - br_float(row.get("val_reducao"))
            rows.append((d, row, valor))

    rows.sort(key=lambda t: t[0])  # cronologico
    if CAP and len(rows) > CAP:
        rows = rows[:CAP]
    print(f"{len(rows)} eventos a ingerir (cap={CAP}) de {os.path.basename(CSV)} ...")

    n = 0
    lsn = -1
    for d, row, valor in rows:
        tipo = (row.get("classificacao_alteracao") or "Credito Suplementar").strip()
        instr = (row.get("tipo_instrumento_legal") or "").strip()
        num = (row.get("numero_documento") or str(n)).strip()
        sigla = "".join(w[0] for w in instr.split()[:3]).upper() or "DOC"
        action_id = f"{sigla}-{num}-{d.year}"
        org = nome(row.get("orgao"))
        acao = (row.get("acao") or "").strip()
        cod_acao = acao.split(" - ", 1)[0] if " - " in acao else acao
        payload = {
            "text": f"{tipo} {action_id}: R$ {valor:,.2f} para {org}.",
            "attributes": {
                "action_id": action_id,
                "ano": d.year,
                "orgao": org,
                "acao_orcamentaria": cod_acao,
                "acao": nome(acao),
                "valor": valor,
                "tipo_alteracao": tipo,
                "data_oficial": d.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
        lsn = db.append(
            "AlteracaoOrcamentaria",
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        n += 1
        if n % 1000 == 0:
            print(f"  {n} ... LSN {lsn}")

    print(f"OK: {n} eventos ingeridos. head LSN {lsn}")
    try:
        print("verify:", db.verify())
    except Exception as e:  # noqa: BLE001
        print("verify falhou:", e)


if __name__ == "__main__":
    main()
