const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = 8082;

// Arquivo gerado pelo worker_mfe.py
const DATA_PATH = path.join(__dirname, "entrada.json");

// Servir index.html e arquivos estáticos da pasta atual
app.use(express.static(__dirname));

app.get("/api/mfe", (req, res) => {
  try {
    if (!fs.existsSync(DATA_PATH)) {
      return res.json([]);
    }

    const raw = fs.readFileSync(DATA_PATH, "utf-8");
    const json = JSON.parse(raw);

    // Suportar tanto formato "lista" quanto "{ posicional: [...] }"
    if (Array.isArray(json)) {
      const ordenado = [...json].sort((a, b) =>
        (a.par || "").localeCompare(b.par || "")
      );
      return res.json(ordenado);
    }

    if (Array.isArray(json.posicional)) {
      const ordenado = [...json.posicional].sort((a, b) =>
        (a.par || "").localeCompare(b.par || "")
      );
      return res.json({
        ...json,
        posicional: ordenado,
      });
    }

    // Se vier em outro formato, devolve como está
    return res.json(json);
  } catch (err) {
    console.error("Erro lendo entrada.json MFE:", err);
    return res.status(500).json([]);
  }
});

app.listen(PORT, () => {
  console.log(`Painel MFE rodando na porta ${PORT}`);
});
