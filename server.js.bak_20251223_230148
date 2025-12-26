const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();

// Porta exclusiva do painel MFE
const PORT = 8082;

// Caminho do JSON gerado pelo worker MFE v2
const ENTRADA_PATH = "/home/roteiro_ds/autotrader-mfe-painel/entrada.json";

// --------- ROTA DE API: /api/mfe ---------
app.get("/api/mfe", (req, res) => {
  try {
    if (!fs.existsSync(ENTRADA_PATH)) {
      return res.json({
        posicional: [],
        ultima_atualizacao: null,
      });
    }

    const raw = fs.readFileSync(ENTRADA_PATH, "utf8");
    let data = JSON.parse(raw);

    // Garantir estrutura mínima
    if (!data || typeof data !== "object") {
      data = { posicional: [], ultima_atualizacao: null };
    }
    if (!Array.isArray(data.posicional)) {
      data.posicional = [];
    }

    return res.json(data);
  } catch (err) {
    console.error("[ERRO] /api/mfe:", err);
    return res.json({
      posicional: [],
      ultima_atualizacao: null,
    });
  }
});

// --------- ROTA PRINCIPAL: / (HTML do painel) ---------
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "index.html"));
});

// --------- INICIAR SERVIDOR ---------
app.listen(PORT, () => {
  console.log(`[MFE] Painel de Entrada MFE ouvindo na porta ${PORT}`);
});
