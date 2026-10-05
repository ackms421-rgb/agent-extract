# ToolFarm — Agent Extract (`url_to_markdown`)

**v1 product:** URL → clean markdown / main-text extract for AI agents.  
**Not in v1:** web search / SERP (later add-on only).

Built for **MCPize** (MCP + x402 USDC metering) and **Ozma** (OpenAPI + Stripe Connect). Fits Steven’s constraints: ~$1k–5k build budget, fully automated after setup, no support inbox.

## Why this, not pure search

Research consensus (MCP Market Scout / ToolFarm Skeptic / Niche Consult): browser automation wins *installs* but is free/ops-heavy; pure search is crowded (Exa/Tavily/Brave). **Paid demand that fits passive ops** is Firecrawl-class **page extract**. Ship extract first; add cheap SERP later only if extract converts.

## Product

| Item | Detail |
|------|--------|
| Tool | `url_to_markdown(url)` |
| Output | Clean markdown/text + title + char_count |
| Guard | SSRF: http/https only; no private/link-local/metadata IPs; credentials in URL banned; redirects re-checked |
| Stack | Python 3.12, FastAPI, httpx, trafilatura |

### Surfaces

- **REST (Ozma):** `POST /v1/url_to_markdown` — OpenAPI at `/openapi.json` and `openapi.yaml`
- **MCP-shaped:** `POST /mcp` — `tools/list` + `tools/call` for `url_to_markdown`
- **Health:** `GET /health`

## Pricing suggestion

| Platform | Metering | Suggested price | Notes |
|----------|----------|-----------------|-------|
| **MCPize** | x402 USDC (Base) | **$0.01–0.02 / call** | Publisher keeps ~80% (platform ~20%). Crypto path works here. |
| **Ozma** | Stripe Connect | ~$0.02 list equivalent | **x402 disabled in Ozma prod** — card/Stripe only; ~10% take. |

COGS target: self-fetch + trafilatura (no Serper in v1). Keep gross margin healthy; do not depend on paid SERP keys for v1.

## Kill switches

Stop or pivot if any of these hit:

1. **&lt; 2k billable extract calls in 60 days** after listing on MCPize (and Ozma if listed).
2. **Gross margin &lt; 40% for 2 consecutive months** (proxy/bandwidth/hosting blow-up).
3. **Platform embeds free equivalent** that zeros paid demand (same failure mode as thin SERP wrappers).
4. **Ops ceases to be passive** (CAPTCHA/proxy whack-a-mole weekly) — then kill or narrow to static/public docs only.
5. **Ozma/MCPize fee change** that makes $0.01–0.02/call underwater after take + COGS.

## Project layout

```
/workspace/toolfarm/agent-extract/
  README.md
  .env.example
  requirements.txt
  Dockerfile
  openapi.yaml          # Ozma import sketch
  pytest.ini
  src/
    main.py             # FastAPI + MCP JSON-RPC
    extract.py          # fetch + trafilatura
    ssrf.py             # SSRF validation
    config.py
  tests/
    test_ssrf.py
    test_extract.py
```

## Run locally

```bash
cd /workspace/toolfarm/agent-extract
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# API
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# Or module entry
python3 -m src.main
```

### Try it

```bash
# Health
curl -s http://127.0.0.1:8080/health

# Extract
curl -s -X POST http://127.0.0.1:8080/v1/url_to_markdown \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/"}'

# MCP tools/list
curl -s -X POST http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Optional: set `API_KEY` in `.env` and send `Authorization: Bearer <key>`.

### Tests

```bash
cd /workspace/toolfarm/agent-extract
source .venv/bin/activate
pytest -q
```

### Docker (no deploy required)

```bash
docker build -t toolfarm-agent-extract .
docker run --rm -p 8080:8080 toolfarm-agent-extract
```

## What is intentionally not here

- No Serper / Exa / Tavily keys (search = later add-on)
- No x402 middleware wired yet (MCPize will attach metering at listing time)
- No production deploy, no paid infra
- No human support inbox — failures return structured `error` fields

## Next steps (when Steven unlocks)

1. Finish MCPize seller account; list MCP tool with x402 price $0.01–0.02.
2. Import `openapi.yaml` (or live `/openapi.json`) into Ozma with Stripe Connect.
3. Add observability (request counts, error rates) without a support queue.
4. Only then consider `agent_serp` as a metered add-on.
