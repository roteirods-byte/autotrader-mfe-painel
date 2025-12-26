# ENTRADA-MFE (AUTOTRADER)

Painel web (Node/Express) + Worker (Python) que gera `entrada.json` e o painel consome via `/api/entrada`.

## Serviços (systemd)
- autotrader-mfe-worker.service
- autotrader-mfe-painel.service

## Endpoints
- /health
- /api/entrada
