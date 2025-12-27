#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
worker_mfe.py
AUTOTRADER – PAINEL DE ENTRADA MFE
Autor: ChatGPT + Jorge
Atualizado: 2025-12-05

Fluxo:
1. Carregar estudos MFE (mfe_estudos.csv)
2. Preço médio Binance + Bybit
3. Calcular 3 alvos p50 / p60 / p70
4. Ganho LONG e SHORT (sempre POSITIVO)
5. Escolher melhor lado
6. Filtrar moedas com ganho ≥ 3%
7. Calcular zona, risco e prioridade
8. Salvar entrada.json no formato do painel MFE
"""

import os
import json
import csv
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time


# ===== PREÇOS (BULK) =====
PRECO_CACHE = {}

def atualizar_precos_bulk(pares):
    """Busca preços em lote via CryptoCompare (USD)."""
    global PRECO_CACHE
    try:
        fsyms = ",".join(pares)
        url = f"https://min-api.cryptocompare.com/data/pricemulti?fsyms={fsyms}&tsyms=USD"
        resp = requests.get(url, timeout=6).json()

        cache = {}
        for sym in pares:
            v = resp.get(sym, {}).get("USD", 0)
            try:
                cache[sym] = float(v) if v else 0.0
            except:
                cache[sym] = 0.0

        PRECO_CACHE = cache
    except:
        PRECO_CACHE = {}

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

# Timezone oficial do projeto
TZ_NAME = os.getenv("APP_TZ", "America/Sao_Paulo")
TZ = ZoneInfo(TZ_NAME)

# Caminho onde o painel lê o JSON (padrão: mesma pasta deste arquivo)
OUTPUT_JSON = os.getenv(
    "OUTPUT_JSON",
    os.path.join(os.path.dirname(__file__), "entrada.json")
)

# Caminho do arquivo de estudos (ajuste via variável de ambiente se necessário)
MFE_CSV = os.getenv(
    "MFE_CSV",
    "/home/roteiro_ds/autotrader-planilhas-python/data/mfe_estudos.csv"
)

# Tempo entre ciclos (5 minutos)
INTERVALO = int(os.getenv("INTERVALO", "300"))

# Rodar só 1 ciclo (para teste): RUN_ONCE=1
RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"

# ============================================================
# UNIVERSO DAS 50 MOEDAS SELECIONADAS
# ============================================================

PARES = [
    "AAVE","ADA","APT","ARB","ATOM","AVAX","AXS","BCH","BNB","BTC",
    "DOGE","DOT","ETH","FET","FIL","FLUX","ICP","INJ","LDO","LINK",
    "LTC","NEAR","OP","PEPE","POL","RATS","RENDER","RUNE","SEI","SHIB",
    "SOL","SUI","TIA","TNSR","TON","TRX","UNI","WIF","XRP","XLM",
    "MATIC","ETC","HBAR","EGLD","SAND","MANA","GALA","NEO","KAVA","CAKE"
]

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def ler_estudos_csv(caminho):
    """Lê mfe_estudos.csv no formato: PAR;LADO;PERCENTIL;ALVO_PCT e monta P50/P60/P70."""
    estudos = {}
    with open(caminho, "r", encoding="utf-8") as f:
        leitor = csv.DictReader(f, delimiter=";")
        for row in leitor:
            par = (row.get("PAR") or "").strip().upper()
            lado = (row.get("LADO") or "").strip().upper()
            perc = (row.get("PERCENTIL") or "").strip()
            alvo = (row.get("ALVO_PCT") or "").strip()

            if not par or lado not in ("LONG", "SHORT"):
                continue
            if perc not in ("50", "60", "70"):
                continue
            try:
                alvo_f = float(alvo)
            except:
                continue

            if par not in estudos:
                estudos[par] = {}
            if lado not in estudos[par]:
                estudos[par][lado] = {}

            estudos[par][lado][f"P{perc}"] = alvo_f

    return estudos


def preco_atual(par):
    """Preço atual vindo do cache (atualizado em lote)."""
    return float(PRECO_CACHE.get(par, 0.0) or 0.0)
def ganho_pct(preco, alvo, side):
    """Ganho percentual (sempre positivo)."""
    if preco <= 0 or alvo <= 0:
        return 0.0

    if side == "LONG":
        return max(0.0, ((alvo - preco) / preco) * 100)
    if side == "SHORT":
        return max(0.0, ((preco - alvo) / preco) * 100)
    return 0.0


def definir_zona(ganho):
    if ganho >= 6:
        return "VERDE"
    if ganho >= 3:
        return "AMARELA"
    return "VERMELHA"


def definir_risco(ganho):
    if ganho >= 6:
        return "BAIXO"
    if ganho >= 3:
        return "MÉDIO"
    return "ALTO"


def definir_prioridade(ganho):
    if ganho >= 8:
        return "ALTA"
    if ganho >= 5:
        return "MÉDIA"
    return "BAIXA"


def calcular_sinal(par, mfe):
    """Retorna sinal no formato do painel ou None.
    OBS: no mfe_estudos.csv o ALVO_PCT é percentual (%), não preço.
    """
    preco = preco_atual(par)
    if preco <= 0:
        return None

    long_data = mfe.get("LONG")
    short_data = mfe.get("SHORT")

    if not long_data and not short_data:
        return None

    # Aqui P50/P60/P70 são % (ALVO_PCT)
    alvo_long_pct = float(long_data.get("P60", 0)) if long_data else 0.0
    alvo_short_pct = float(short_data.get("P60", 0)) if short_data else 0.0

    # Converter % -> preço alvo
    alvo_long_preco = preco * (1 + (alvo_long_pct / 100.0)) if alvo_long_pct > 0 else 0.0
    alvo_short_preco = preco * (1 - (alvo_short_pct / 100.0)) if alvo_short_pct > 0 else 0.0

    g_long = ganho_pct(preco, alvo_long_preco, "LONG") if alvo_long_preco else 0.0
    g_short = ganho_pct(preco, alvo_short_preco, "SHORT") if alvo_short_preco else 0.0

    if g_long <= 0 and g_short <= 0:
        return None

    side = "LONG" if g_long >= g_short else "SHORT"
    alvo = alvo_long_preco if side == "LONG" else alvo_short_preco
    ganho = g_long if side == "LONG" else g_short

    if ganho < 3:
        return None

    zona = definir_zona(ganho)
    risco = definir_risco(ganho)
    prioridade = definir_prioridade(ganho)

    agora = datetime.now(TZ)
    data = agora.strftime("%Y-%m-%d")
    hora = agora.strftime("%H:%M")

    return {
        "par": par,
        "side": side,
        "preco": float(preco),
        "alvo": float(alvo),
        "ganho_pct": round(float(ganho), 2),
        "zona": zona,
        "risco": risco,
        "prioridade": prioridade,
        "data": data,
        "hora": hora
    }


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def loop():
    print(f"[MFE] TZ={TZ_NAME} | OUTPUT_JSON={OUTPUT_JSON} | MFE_CSV={MFE_CSV}")
    while True:
        try:
            estudos = ler_estudos_csv(MFE_CSV)


            atualizar_precos_bulk(PARES)
            sinais = []
            for par in PARES:
                mfe = estudos.get(par)
                if not mfe:
                    continue
                sinal = calcular_sinal(par, mfe)
                if sinal:
                    sinais.append(sinal)

            # Ordenar por maior ganho
            sinais.sort(key=lambda x: x["ganho_pct"], reverse=True)

            # Gravar JSON
            saida = {
                "posicional": sinais,
                "ultima_atualizacao": datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
            }

            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(saida, f, indent=2, ensure_ascii=False)

            print(f"[OK] Atualizado: {saida['ultima_atualizacao']} | Total exibidas: {len(sinais)}")

        except Exception as e:
            print("ERRO NO LOOP:", e)

        if RUN_ONCE:
            break

        time.sleep(INTERVALO)


if __name__ == "__main__":
    loop()
