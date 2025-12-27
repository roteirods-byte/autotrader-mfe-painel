#!/usr/bin/env python3
import os, json, time, urllib.request, urllib.error

INPUT_JSON  = os.environ.get("OUTPUT_JSON", "/home/roteiro_ds/ENTRADA-MFE/entrada.json")
COINS_FILE  = os.environ.get("MFE_COINS_FILE", "/home/roteiro_ds/ENTRADA-MFE/coins_77.txt")

def read_coins(path):
    coins = []
    if not os.path.isfile(path):
        return coins
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip().upper()
            if not s or s.startswith("#"): 
                continue
            # aceita só token “limpo”
            if all(ch.isalnum() for ch in s) and 2 <= len(s) <= 10 and "USDT" not in s:
                coins.append(s)
    # únicos, em ordem
    out = []
    seen = set()
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
    # fallback: se coins_77.txt não existir, mantém o que já tem
    base_list = data.get("posicional", [])
    by_par = { (it.get("par","") or "").upper(): it for it in base_list if isinstance(it, dict) }

    # pega preços (1 chamada só)
    prices = fetch_binance_prices()

    ultima = data.get("ultima_atualizacao") or ""
    # força data/hora das linhas = hora do cálculo (não “hora do PC”)
    calc_data = ""
    calc_hora = ""
    if isinstance(ultima, str) and len(ultima) >= 16:
        # aceita "YYYY-MM-DD HH:MM" ou "YYYY-MM-DD HH:MM:SS"
        calc_data = ultima[0:10]
        calc_hora = ultima[11:16]

    def price_for(coin, fallback=0.0):
        sym = f"{coin}USDT"
        p = prices.get(sym)
        if p is None:
            return fallback
        try:
            return float(p)
        except:
            return fallback

    out_rows = []
    sinais = 0

    # se tiver coins, força 1 linha por coin
    if coins:
        for c in coins:
            it = dict(by_par.get(c, {}))
            if not it:
                it = {"par": c}

            side = (it.get("side") or "NÃO ENTRAR")
            it["side"] = side

            # preço: se não veio do worker, pega do Binance
            try:
                cur = float(it.get("preco") or 0.0)
            except:
                cur = 0.0
            if cur <= 0:
                cur = price_for(c, 0.0)
            it["preco"] = cur

            # campos obrigatórios (não deixa vazio)
            it.setdefault("alvo", 0.0)
            it.setdefault("ganho_pct", 0.0)
            it.setdefault("assertividade", "")
            it.setdefault("score", "")
            it.setdefault("zona", "—")
            it.setdefault("risco", "—")
            it.setdefault("prioridade", "—")

            # data/hora = hora do cálculo
            if calc_data: it["data"] = calc_data
            if calc_hora: it["hora"] = calc_hora

            # conta sinais reais
            if str(side).upper() in ("LONG","SHORT"):
                sinais += 1

            out_rows.append(it)

        # ordena por PAR
        out_rows.sort(key=lambda x: (x.get("par","") or ""))

    else:
        # sem lista: mantém o que já existe
        out_rows = base_list

    data["posicional"] = out_rows
    data["total_moedas"] = len(out_rows)
    data["total_sinais"] = sinais

    atomic_write_json(INPUT_JSON, data)

if __name__ == "__main__":
    main()
