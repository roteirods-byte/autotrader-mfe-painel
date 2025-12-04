// server.js
// Servidor do Painel MFE Posicional
// - Serve o index.html
// - GET /api/mfe: lê o POSICIONAL de entrada.json e monta os campos do painel

const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 8082;

// Caminho do JSON já gerado pela automação (painel antigo, blindado)
const ENTRADA_PATH =
  "/home/roteiro_ds/autotrader-planilhas-python/data/entrada.json";

// ---------- CLASSIFICAÇÕES AUXILIARES ----------

const RISCO_BAIXO = new Set([
  "BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "TRX", "LTC",
  "LINK", "ATOM", "NEAR", "OP", "UNI", "POL", "TIA",
]);

const RISCO_ALTO = new Set([
  "ICP", "FET", "FLUX", "PEPE", "WIF", "GALA", "MANA",
  "SAND", "TNSR", "SEI", "AXS", "RUNE",
]);

function classificarRisco(par) {
  if (RISCO_BAIXO.has(par)) return "BAIXO";
  if (RISCO_ALTO.has(par)) return "ALTO";
  return "MÉDIO";
}

function classificarZona(ganhoAbs) {
  if (ganhoAbs <= 0) return "-";
  if (ganhoAbs < 3) return "AMARELA";   // pouco ganho
  if (ganhoAbs <= 8) return "VERDE";    // zona ideal
  return "VERMELHA";                    // muito agressivo
}

function classificarPrioridade(side, ganhoAbs, risco, assertPct) {
  if (side === "NAO_ENTRAR") return "NÃO OPERAR";

  let prioridade = "BAIXA";

  if (ganhoAbs >= 3 && ganhoAbs <= 8 && (risco === "BAIXO" || risco === "MÉDIO")) {
    prioridade = "MÉDIA";
  }
  if (ganhoAbs >= 4 && risco === "BAIXO") {
    prioridade = "ALTA";
  }
  if (ganhoAbs >= 6 && risco === "BAIXO") {
    prioridade = "ALTA";
  }

  if (typeof assertPct === "number" && assertPct < 65) {
    prioridade = "BAIXA";
  }

  return prioridade;
}

// Lê o POSICIONAL do entrada.json e monta a lista para o painel
function montarPainelAPartirDeEntrada() {
  if (!fs.existsSync(ENTRADA_PATH)) {
    return null;
  }

  const raw = fs.readFileSync(ENTRADA_PATH, "utf-8");
  const json = JSON.parse(raw);

  // Estrutura esperada: { swing: [...], posicional: [...], ultima_atualizacao: "..." }
  const listaPosicional = Array.isArray(json.posicional) ? json.posicional : [];

  const saida = listaPosicional.map((item) => {
    const sideRaw = item.side || item.sinal || item.SIDE || "NAO_ENTRAR";

    const ganhoBruto = typeof item.ganho_pct === "number" ? item.ganho_pct : 0;
    const ganhoAbs = Math.abs(ganhoBruto); // GANHO SEMPRE POSITIVO

    const risco = classificarRisco(item.par);
    const zona = classificarZona(ganhoAbs);
    const prioridade = classificarPrioridade(
      sideRaw,
      ganhoAbs,
      risco,
      item.assert_pct
    );

    return {
      par: item.par,
      side: sideRaw,
      preco: item.preco,
      alvo: item.alvo,
      ganho_pct: ganhoAbs,      // já em valor absoluto
      zona,
      risco,
      prioridade,
      data: item.data,
      hora: item.hora,
    };
  });

  return {
    registros: saida,
    ultima_atualizacao: json.ultima_atualizacao || null,
  };
}

app.use(express.json());
const publicDir = path.join(__dirname);
app.use(express.static(publicDir));

// ---------- ROTA API /api/mfe ----------
app.get("/api/mfe", (req, res) => {
  try {
    const resultado = montarPainelAPartirDeEntrada();
    if (!resultado || resultado.registros.length === 0) {
      return res.json([]); // sem fallback: se não tiver nada, o front avisa
    }
    return res.json(resultado.registros);
  } catch (err) {
    console.error("Erro em /api/mfe:", err);
    return res.json([]);
  }
});

// ---------- ROTA RAIZ ----------
app.get("/", (req, res) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

// ---------- START ----------
app.listen(PORT, () => {
  console.log(`Painel MFE rodando na porta ${PORT}`);
});
