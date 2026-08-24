# ShopAgent

A conversational shopping assistant that lets a user discover products, manage a cart, and check out — all through natural language.

This project was made as part of the training program on Agents, FastAPI and Stripe.

## Quick start

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

python -m venv .venv
source .venv/bin/activate

docker compose up -d
pip install -r requirements.txt
python -m shopagent.seed
python -m shopagent
```

Compose starts Postgres with pgvector. The app runs on the host: seed the catalog from `data/catalog.json` (which also refreshes OpenAI embeddings), then start the CLI.

`python -m shopagent` starts a stdio MCP child (`shopagent.mcp_server`) and the agent dynamically loads catalog/cart tools from that server. Product and cart answers go only through MCP — the CLI does not call the catalog directly.

Re-run `python -m shopagent.seed` whenever you change `data/catalog.json` (it always refreshes embeddings).

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |
| `OPENAI_MODEL` | Model name: `gpt-4.1-mini` (default), `gpt-4.1`, `gpt-4.1-nano`, `gpt-4o`, or `gpt-4o-mini` |
| `TEMPERATURE` | Sampling temperature (default `0.7`) |
| `DATABASE_URL` | Postgres URL (default uses `localhost` against Compose `db`) |
| `OPENAI_EMBEDDING_MODEL` | Embedding model for semantic search (default `text-embedding-3-small`) |

### Supported models and pricing

Pricing is defined in `config.py` (USD per 1M tokens). These models support the `temperature` parameter:

| Model | Input | Output |
|-------|-------|--------|
| `gpt-4.1` | $2.00 | $8.00 |
| `gpt-4.1-mini` (default) | $0.40 | $1.60 |
| `gpt-4.1-nano` | $0.10 | $0.40 |
| `gpt-4o` | $2.50 | $10.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |

## Note on GPT-5 and temperature

The GPT-5 family uses controls such as `reasoning_effort` and `verbosity` instead of allowing to tune with temperature. Attempting to set a non-default temperature on GPT-5 models will result in an "Unsupported parameter" error.

## MCP server (stdio)

ShopAgent runs as an [MCP](https://modelcontextprotocol.io/) server that exposes the catalog and cart tools (`filter_products`, `semantic_search`, `get_product`, `check_stock`, `add_to_cart`, `calculate_cart_total`) over stdio. The cart is in-memory for the life of the process.

The CLI agent connects to this server automatically (one child process per session), lists tools via MCP, and invokes them with `call_tool`. You can also talk to the same server from the MCP Inspector.

Prerequisites are the same as the CLI: Compose DB up, catalog seeded, and `.env` configured (`DATABASE_URL` required; `OPENAI_API_KEY` required for semantic search). You also need `npx` on your `PATH` (Node.js) for the Inspector UI.

### MCP Inspector

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npx @modelcontextprotocol/inspector
```

Open the URL printed in the terminal, then use **Add server** with:

| Field | Value |
|-------|--------|
| Server ID | `shopagent` |
| Transport | `stdio (local process)` |
| Command | absolute path to your venv Python, e.g. `/path/to/shop-agent/.venv/bin/python` |
| Arguments | one per line: `-m` then `shopagent.mcp_server` |
| Environment | one `KEY=VALUE` per line — at least `DATABASE_URL=...` and `OPENAI_API_KEY=...` (same values as `.env`) |
| Working directory | absolute path to the repo root, e.g. `/path/to/shop-agent` |

After **Add**, connect to the server, open **Tools**, and try `filter_products` (`category=Running`), then `add_to_cart` / `calculate_cart_total`.
