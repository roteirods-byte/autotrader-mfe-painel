"use strict";

const fs = require("fs");
const path = require("path");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 8082;

const ROOT = __dirname;
const INDEX_HTML = path.join(ROOT, "index.html");

// JSON que o worker grava (não mexe no worker)
const ENTRADA_PATH = process.env.ENTRADA_JSON || "/home/roteiro_ds/ENTRADA-MFE/entrada.json";

// Lista 77 moedas (1 por linha)
const UNIVERSE_TXT = process.env.MFE_UNIVERSE_TXT || path.join(ROOT, "coins_77.txt");

let LAST_OK = null; // último JSON bom (para fallback)

function brtNowParts() {
  const d = new Date();
  const fmt = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const parts = fmt.formatToParts(d).reduce((acc, p) => {
    acc[p.type] = p.value;
    return acc;
  }, {});
  const date = `${parts.year}-${parts.month}-${parts.day}`;
  const time = `${parts.hour}:${parts.minute}`;
  const datetime = `${date} ${time}:${parts.second}`;
  return { date, time, datetime };
}

function uniqUpper(arr) {
  const out = [];
  const seen = new Set();
  for (const x of arr) {
    const v = String(x || "").trim().toUpperCase();
    if (!v) continue;
    if (seen.has(v)) continue;
    seen.add(v);
    out.push(v);
  }
  return out;
}

function loadUniverse(fallbackList) {
  // 1) ENV: MFE_UNIVERSE="BTC,ETH,..."
  if (process.env.MFE_UNIVERSE) {
    return uniqUpper(process.env.MFE_UNIVERSE.split(","));
  }

  // 2) arquivo coins_77.txt
  try {
    if (fs.existsSync(UNIVERSE_TXT)) {
      const raw = fs.readFileSync(UNIVERSE_TXT, "utf8");
      const lines = raw
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter((l) => l && !l.startsWith("#"));
      const uni = uniqUpper(lines);
      if (uni.length) return uni;
    }
  } catch (_) {}

  // 3) fallback: o que veio no JSON
  return uniqUpper((fallbackList || []).map((x) => x.par));
}

function readJsonSafe() {
  const raw = fs.readFileSync(ENTRADA_PATH, "utf8").trim();
  if (!raw) throw new Error("arquivo vazio");
  const data = JSON.parse(raw);

  const list = Array.isArray(data.posicional) ? data.posicional : [];
  const ultima = (data.ultima_atualizacao || "").toString().trim();

  return {
    posicional: list,
    ultima_atualizacao: ultima,
    gain_min: data.gain_min,
    assert_min: data.assert_min,
  };
}

function normalizeItem(it, now) {
  // garante campos (sem inventar cálculo)
  const par = String(it.par || "").trim().toUpperCase();
  const side = (it.side ?? "").toString();
  return {
    par,
    side,
    preco: it.preco ?? "",
    alvo: it.alvo ?? "",
    ganho_pct: it.ganho_pct ?? "",
    assertividade: it.assertividade ?? "",
    score: it.score ?? "",
    zona: it.zona ?? "",
    risco: it.risco ?? "",
    prioridade: it.prioridade ?? "",
    data: it.data ?? now.date,
    hora: it.hora ?? now.time,
  };
}

function fillToUniverse(list, universe, now) {
  const map = new Map();
  for (const it of list || []) {
    const par = String(it.par || "").trim().toUpperCase();
    if (!par) continue;
    map.set(par, normalizeItem(it, now));
  }

  const out = [];
  for (const par of universe) {
    if (map.has(par)) {
      out.push(map.get(par));
    } else {
      // moeda sem dado/calculo: NÃO ENTRAR (sem inventar preco/alvo)
      out.push({
        par,
        side: "NÃO ENTRAR",
        preco: "",
        alvo: "",
        ganho_pct: "",
        assertividade: "",
        score: "",
        zona: "",
        risco: "",
        prioridade: "",
        data: now.date,
        hora: now.time,
      });
    }
  }
  return out;
}

function countSignals(list) {
  let n = 0;
  for (const it of list || []) {
    const s = String(it.side || "").toUpperCase();
    if (s === "LONG" || s === "SHORT") n++;
  }
  return n;
}

// static
app.use((req, res, next) => {
  res.setHeader("Cache-Control", "no-store");
  next();
});
app.use(express.static(ROOT));

app.get("/", (_, res) => res.sendFile(INDEX_HTML));

app.get("/health", (req, res) => {
  const now = brtNowParts();
  res.json({ ok: true, server_now: now.datetime });
});

app.get("/api/entrada", (req, res) => {
  const now = brtNowParts();

  let data;
  let stale = false;

  try {
    data = readJsonSafe();
    LAST_OK = data;
  } catch (e) {
    stale = true;
    data = LAST_OK || { posicional: [], ultima_atualizacao: "", gain_min: null, assert_min: null };
  }

  const universe = loadUniverse(data.posicional);
  const filled = fillToUniverse(data.posicional, universe, now);

  res.json({
    posicional: filled,
    ultima_atualizacao: data.ultima_atualizacao || "",
    stale,
    server_now: now.datetime,
    server_date: now.date,
    server_time: now.time,
    universo_total: universe.length,
    total_exibidas: filled.length,
    total_sinais: countSignals(filled),
    gain_min: data.gain_min ?? null,
    assert_min: data.assert_min ?? null,
  });


// TOP10 (arquivo gerado pelo mfe_enrich.py)
const TOP10_JSON = process.env.TOP10_JSON || path.join(ROOT, "top10.json");

app.get("/api/top10", (req,res)=>{
  try{
    const raw = fs.readFileSync(TOP10_JSON, "utf-8");
    res.setHeader("Content-Type","application/json; charset=utf-8");
    res.send(raw);
  }catch(e){
    res.status(200).json({ agora_brt:"", ultimo_calculo_brt:"", total_top:0, total_sinais_top:0, top10:[] });
  }
});

app.get("/top10", (req,res)=>{
  res.sendFile(path.join(ROOT, "top10.html"));
});
});
// ===== TOP10 (MFE) =====
const TOP10_JSON = process.env.TOP10_JSON || path.join(ROOT, "top10.json");

app.get("/api/top10", (req, res) => {
  try {
    const raw = fs.readFileSync(TOP10_JSON, "utf-8");
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.send(raw);
  } catch (e) {
    res.status(200).json({ agora_brt:"", ultimo_calculo_brt:"", total_top:0, total_sinais_top:0, top10:[] });
  }
});

app.get("/top10", (req, res) => {
  res.sendFile(path.join(ROOT, "top10.html"));
});
// =========================



app.listen(PORT, () => {
  const now = brtNowParts();
  console.log(`[MFE] Panel ouvindo na porta ${PORT} | BRT ${now.datetime}`);
  console.log(`[MFE] JSON: ${ENTRADA_PATH}`);
  console.log(`[MFE] UNIVERSE_TXT: ${UNIVERSE_TXT}`);
});
