#!/usr/bin/env python3
import os, json, time, re, urllib.request

INPUT_JSON  = os.environ.get("OUTPUT_JSON", "/home/roteiro_ds/ENTRADA-MFE/entrada.json")
COINS_FILE  = os.environ.get("MFE_COINS_FILE", "/home/roteiro_ds/ENTRADA-MFE/coins_77.txt")
TOP10_JSON  = os.environ.get("TOP10_JSON", "/home/roteiro_ds/ENTRADA-MFE/top10.json")

MAX_COINS = 200  # trava anti-explosão

def is_valid_coin(s: str) -> bool:
    if not s: return False
    s = s.strip().upper()
    if "USDT" in s: return False
    if not s.isalnum(): return False
    if not (2 <= len(s) <= 10): return False
    if not any(ch.isalpha() for ch in s): return False   # obrigatório ter letra
    if re.fullmatch(r"[0-9A-F]{2,10}", s): return False   # bloqueia “hex puro”
    return True

def read_coins(path):
    coins = []
    if not os.path.isfile(path):
        return coins
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip().upper()
            if not s or s.startswith("#"):
                continue
            if is_valid_coin(s):
                coins.append(s)
    # únicos
    out, seen = [], set()
    for c in coins:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out

def fetch_binance_prices():
    url = "https://api.binance.com/api/v3/ticker/price"
    mp = {}
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        for it in data:
            sym = it.get("symbol","")
            pr  = it.get("price","")
            if sym and pr:
                mp[sym] = pr
    except Exception:
        pass
    return mp

def atomic_write_json(path, obj):
    d = os.path.dirname(path) or "."
    tmp = os.path.join(d, f".tmp_{int(time.time())}_{os.getpid()}.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",",":"))
    os.replace(tmp, path)

def now_brt_str():
    # sua VM já está em -03 (BRT) pelos logs
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def main():
    if not os.path.isfile(INPUT_JSON):
        return

    raw = open(INPUT_JSON, "r", encoding="utf-8", errors="ignore").read().strip()
    if not raw:
        return

    try:
        data = json.loads(raw)
    except Exception:
        return

    coins = read_coins(COINS_FILE)
    if len(coins) > MAX_COINS:
        print(f"[WARN] coins_file explosivo: {len(coins)} > {MAX_COINS}. Mantendo JSON atual.")
        return

    base_list = data.get("posicional", [])
    by_par = { (it.get("par") or "").upper(): it for it in base_list if isinstance(it, dict) }

    prices = fetch_binance_prices()

    ultima = data.get("ultima_atualizacao") or ""
    calc_data = ""
    calc_hora = ""
    if isinstance(ultima, str) and len(ultima) >= 16:
        calc_data = ultima[0:10]
        calc_hora = ultima[11:16]

    def price_for(coin, fallback=0.0):
        sym = f"{coin}USDT"
        p = prices.get(sym)
        if p is None:
            return fallback
        try:
            return float(p)
        except Exception:
            return fallback

    out_rows = []
    if coins:
        for c in coins:
            it = dict(by_par.get(c, {}))
            if not it:
                it = {"par": c}

            side = (it.get("side") or "NÃO ENTRAR")
            it["side"] = side

            cur = to_float(it.get("preco"), 0.0)
            if cur <= 0:
                cur = price_for(c, 0.0)
            it["preco"] = cur

            it.setdefault("alvo", 0.0)
            it.setdefault("ganho_pct", 0.0)
            it.setdefault("assertividade", "")
            it.setdefault("score", "")
            it.setdefault("zona", "-")
            it.setdefault("risco", "-")
            it.setdefault("prioridade", "-")

            if calc_data: it["data"] = calc_data
            if calc_hora: it["hora"] = calc_hora

            out_rows.append(it)

        out_rows.sort(key=lambda x: (x.get("par","") or ""))
    else:
        out_rows = base_list

    # ---- totais oficiais ----
    total_universo = len(out_rows)
    total_sinais_universo = sum(1 for r in out_rows if str(r.get("side","")).upper() in ("LONG","SHORT"))

    data["posicional"] = out_rows
    data["total_moedas"] = total_universo
    data["total_sinais"] = total_sinais_universo
    atomic_write_json(INPUT_JSON, data)

    # ---- TOP10 profissional ----
    sinais_validos = []
    for r in out_rows:
        side = str(r.get("side","")).upper()
        preco = to_float(r.get("preco"), 0.0)
        alvo  = to_float(r.get("alvo"), 0.0)
        ganho = to_float(r.get("ganho_pct"), 0.0)

        # entra no TOP só se for sinal real e com preço/alvo válidos
        if side not in ("LONG","SHORT"):
            continue
        if preco <= 0 or alvo <= 0:
            continue
        if ganho <= 0:
            continue

        sinais_validos.append(r)

    sinais_validos.sort(key=lambda r: to_float(r.get("ganho_pct"), 0.0), reverse=True)
    top10 = sinais_validos[:10]

    payload = {
        "agora_brt": now_brt_str(),
        "ultimo_calculo_brt": (ultima if isinstance(ultima,str) else ""),
        "total_universo": total_universo,
        "total_sinais_universo": total_sinais_universo,
        "exibindo": len(top10),
        "top10": top10,
    }
    atomic_write_json(TOP10_JSON, payload)

if __name__ == "__main__":
    main()
