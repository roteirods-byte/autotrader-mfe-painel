#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, csv, time, math, tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

CSV_PATH = os.environ.get("MFE_CSV", "/home/roteiro_ds/autotrader-planilhas-python/data/mfe_estudos.csv")
PRICES_PATH = os.environ.get("MFE_PRICES_JSON", "/home/roteiro_ds/ENTRADA-MFE/precos_cache.json")
OUT_JSON = os.environ.get("ENTRADA_JSON", "/home/roteiro_ds/ENTRADA-MFE/entrada.json")

ASSERT_MIN = float(os.environ.get("ASSERT_MIN", "65"))   # usa PERCENTIL como “assertividade”
GAIN_MIN   = float(os.environ.get("GAIN_MIN", "3"))      # ALVO_PCT mínimo

# ---- util ----
def now_brt():
    return datetime.now(TZ)

def atomic_write_json(path: str, obj: dict):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def load_prices_any(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    prices = {}
    # aceita formatos comuns
    if isinstance(data, dict):
        # { "AAVE": 123.4 } ou { "prices": { "AAVE": 123.4 } }
        if all(isinstance(v, (int, float)) for v in data.values()):
            for k,v in data.items():
                prices[str(k).upper()] = float(v)
            return prices
        if "prices" in data and isinstance(data["prices"], dict):
            for k,v in data["prices"].items():
                if isinstance(v, (int,float)):
                    prices[str(k).upper()] = float(v)
            return prices
        # varre níveis (1 nível) procurando números
        for k,v in data.items():
            if isinstance(v, dict):
                for kk,vv in v.items():
                    if isinstance(vv,(int,float)):
                        prices[str(kk).upper()] = float(vv)
    return prices

def zone_from_percentil(p: float) -> str:
    if p >= 70: return "VERDE"
    if p >= 50: return "AMARELA"
    return "VERMELHA"

def risco_from_percentil(p: float) -> str:
    if p >= 70: return "BAIXO"
    if p >= 50: return "MÉDIO"
    return "ALTO"

def prioridade_from_gain(g: float, zona: str) -> str:
    # regra conservadora e estável (pode ajustar depois)
    if zona == "VERDE" and g >= 10: return "ALTA"
    if g >= 5: return "MÉDIA"
    return "BAIXA"

def to_float(x):
    try:
        if x is None: return None
        s = str(x).strip().replace(",", ".")
        if s == "": return None
        return float(s)
    except Exception:
        return None

# ---- load estudos ----
def load_estudos(csv_path: str):
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter=";")
        # precisa dessas colunas
        need = {"PAR","LADO","PERCENTIL","ALVO_PCT"}
        if not need.issubset(set([c.strip().upper() for c in r.fieldnames or []])):
            raise RuntimeError("CSV inválido: esperado colunas PAR;LADO;PERCENTIL;ALVO_PCT")
        for row in r:
            par = (row.get("PAR") or "").strip().upper()
            lado = (row.get("LADO") or "").strip().upper()
            p = to_float(row.get("PERCENTIL"))
            alvo_pct = to_float(row.get("ALVO_PCT"))
            if not par:
                continue
            rows.append({
                "PAR": par,
                "LADO": "LONG" if "LONG" in lado else ("SHORT" if "SHORT" in lado else lado),
                "PERCENTIL": 0.0 if p is None else p,
                "ALVO_PCT": 0.0 if alvo_pct is None else alvo_pct,
            })
    return rows

def choose_best_per_par(rows):
    # Se CSV tiver várias linhas do mesmo PAR, escolhe 1 (melhor “score”)
    best = {}
    for r in rows:
        par = r["PAR"]
        score = (r["ALVO_PCT"] * (r["PERCENTIL"]/100.0))
        if (par not in best) or (score > best[par]["_SCORE"]):
            rr = dict(r)
            rr["_SCORE"] = score
            best[par] = rr
    return [best[k] for k in sorted(best.keys())]

def build_output():
    prices = load_prices_any(PRICES_PATH)
    estudos = load_estudos(CSV_PATH)
    escolhidos = choose_best_per_par(estudos)

    t = now_brt()
    data_str = t.strftime("%Y-%m-%d")
    hora_str = t.strftime("%H:%M")

    out_rows = []
    total_sinais = 0

    for e in escolhidos:
        par = e["PAR"]
        lado = e["LADO"]
        percentil = float(e["PERCENTIL"])
        alvo_pct = float(e["ALVO_PCT"])

        preco = float(prices.get(par, 0.0) or 0.0)

        # Filtro oficial (se não bate mínimo, vira “NÃO ENTRAR”)
        if percentil < ASSERT_MIN or alvo_pct < GAIN_MIN or preco <= 0:
            side = "NÃO ENTRAR"
            alvo = ""
            ganho_pct = ""
        else:
            side = lado if lado in ("LONG","SHORT") else "NÃO ENTRAR"
            if side == "LONG":
                alvo = round(preco * (1.0 + alvo_pct/100.0), 3)
            elif side == "SHORT":
                alvo = round(preco * (1.0 - alvo_pct/100.0), 3)
            else:
                alvo = ""
            ganho_pct = round(alvo_pct, 2)
            if side != "NÃO ENTRAR":
                total_sinais += 1

        zona = zone_from_percentil(percentil)
        risco = risco_from_percentil(percentil)
        prioridade = prioridade_from_gain(float(alvo_pct), zona)

        out_rows.append({
            "par": par,
            "side": side,
            "preco": round(preco, 3) if preco else 0.0,
            "alvo": alvo if alvo != "" else "",
            "ganho_pct": ganho_pct if ganho_pct != "" else "",
            "zona": zona,
            "risco": risco,
            "prioridade": prioridade,
            "data": data_str,
            "hora": hora_str,
        })

    payload = {
        "posicional": out_rows,
        "ultima_atualizacao": f"{data_str} {hora_str}",
        "server_now": f"{data_str} {hora_str}",
        "assert_min": ASSERT_MIN,
        "gain_min": GAIN_MIN,
        "total_sinais": total_sinais,
    }
    return payload

def main():
    payload = build_output()

    # Regra crítica: se der qualquer problema grave, NÃO apagar o último JSON
    # Aqui só escreve se payload tem lista não vazia.
    if not isinstance(payload.get("posicional"), list) or len(payload["posicional"]) == 0:
        raise RuntimeError("Sem linhas para escrever (posicional vazio).")

    atomic_write_json(OUT_JSON, payload)

    print(f"[OK] Atualizado: {payload.get('ultima_atualizacao')} | Total exibidas: {len(payload['posicional'])} | Total sinais: {payload.get('total_sinais')}")

if __name__ == "__main__":
    main()
