const fs = require("fs");
const path = require("path");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 8082;

// caminhos (fixos) no disco
const ROOT = "/home/roteiro_ds/ENTRADA-MFE";
const INDEX_HTML = path.join(ROOT, "index.html");
const JSON_PATH = path.join(ROOT, "entrada.json");

// headers
app.use((req, res, next) => {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Pragma", "no-cache");
  res.setHeader("Expires", "0");
  next();
});

// página
app.get("/", (req, res) => res.sendFile(INDEX_HTML));

// API (2 rotas -> mesmo JSON)
function sendJson(res) {
  try {
    const raw = fs.readFileSync(JSON_PATH, "utf-8");
    JSON.parse(raw); // valida
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    return res.status(200).send(raw);
  } catch (e) {
    return res.status(200).json({
      posicional: [],
      ultima_atualizacao: null,
      erro_api: String(e && e.message ? e.message : e),
      json_path: JSON_PATH
    });
  }
}

app.get("/api/mfe", (req, res) => sendJson(res));
app.get("/api/entrada", (req, res) => sendJson(res));

// health
app.get("/health", (req, res) => res.status(200).send("ok"));

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[MFE] Painel de Entrada MFE ouvindo na porta ${PORT}`);
  console.log(`[MFE] JSON: ${JSON_PATH}`);
});
