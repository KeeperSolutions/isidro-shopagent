# ShopAgent

A conversational shopping assistant that lets a user discover products, manage a cart, and check out — all through natural language.

This project was made as part of the training program on Agents, FastAPI and Stripe.

## Quick start

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY and STRIPE_SECRET_KEY

python -m venv .venv
source .venv/bin/activate

docker compose up -d
pip install -r requirements.txt
python -m shopagent.seed
```

Compose starts Postgres with pgvector. The app runs on the host: seed the catalog from `data/catalog.json` (which also refreshes OpenAI embeddings and syncs Products & Prices to Stripe when `STRIPE_SECRET_KEY` is set), then start the HTTP API and the CLI.

Cart and checkout tools call the FastAPI service, so create an API key, put it in `.env` as `SHOPAGENT_API_KEY`, and leave `fastapi dev` running before you start the agent:

```bash
python -m shopagent.create_api_key
# paste the printed sa_... value into .env as SHOPAGENT_API_KEY

fastapi dev   # in another terminal
python -m shopagent
```

`python -m shopagent` starts a stdio MCP child (`shopagent.mcp_server`) and the agent dynamically loads catalog, cart, checkout, and memory tools from that server. Product search still goes through MCP to Postgres. Cart, totals, and checkout go through MCP to FastAPI (`SHOPAGENT_API_URL`, default `http://127.0.0.1:8000`).

The agent keeps short-term cart context in the conversation (a live cart snapshot is injected each turn) and long-term shopper name/preferences in `data/shopper_memory.json`.

Re-run `python -m shopagent.seed` whenever you change `data/catalog.json` (it always refreshes embeddings, then upserts Stripe Products/Prices keyed by catalog UUID and SKU).

## HTTP API (cart & orders)

With Compose running and the catalog seeded, create an API key (the plaintext value is shown once; only a SHA-256 hash is stored):

```bash
python -m shopagent.create_api_key
```

Then:

```bash
fastapi dev
```

Cart, order, and checkout-create endpoints require the `X-API-Key` header. Each key may have **one active cart** at a time and can only read carts and orders it owns. Stripe redirects the browser to the public success/cancel URLs (no API key).

Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Hello message |
| POST | `/cart` | Create a new cart |
| GET | `/cart` | View your active cart |
| GET | `/cart/{cart_id}` | View a cart owned by this key |
| POST | `/cart/{cart_id}/items` | Add a variant by SKU to your active cart |
| GET | `/orders` | List orders owned by this key (newest first); used to resume a pending checkout |
| POST | `/orders` | Create an order from an active cart (`{"cart_id": "..."}`) — rejects an empty cart and re-checks stock; starts as `pending`; does not retire the cart |
| GET | `/orders/{order_id}` | Fetch an order |
| POST | `/orders/{order_id}/refund` | Full Stripe refund of a `paid` order |
| POST | `/checkout` | Create a Stripe Checkout Session for a pending order (`{"order_id": "..."}`); retires the cart only after Stripe returns a URL |
| POST | `/webhooks/stripe` | Stripe webhooks |

Forward local events with the Stripe CLI:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
# put the printed whsec_... into .env as STRIPE_WEBHOOK_SECRET
```

Handled events: `checkout.session.completed`, `payment_intent.succeeded`.

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |
| `OPENAI_MODEL` | Model name: `gpt-4.1-mini` (default), `gpt-4.1`, `gpt-4.1-nano`, `gpt-4o`, or `gpt-4o-mini` |
| `TEMPERATURE` | Sampling temperature (default `0.7`) |
| `DATABASE_URL` | Postgres URL (default uses `localhost` against Compose `db`) |
| `OPENAI_EMBEDDING_MODEL` | Embedding model for semantic search (default `text-embedding-3-small`) |
| `STRIPE_SECRET_KEY` | Stripe secret key (test-mode `sk_test_...`; Checkout Sessions and catalog Product/Price sync) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`whsec_...`) for `POST /webhooks/stripe` |
| `SHOPAGENT_API_URL` | FastAPI base URL for cart/checkout tools (default `http://127.0.0.1:8000`) |
| `SHOPAGENT_API_KEY` | API key from `python -m shopagent.create_api_key` (required for cart, totals, and checkout) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key (optional; tracing is off when unset) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_BASE_URL` | Langfuse host (default `https://cloud.langfuse.com`) |

### Langfuse tracing

When Langfuse keys are set, each shopper turn is one trace (`handle-user-message`) and the whole CLI conversation is one [session](https://langfuse.com/docs/observability/features/sessions). OpenAI calls nest as generations (model, tokens, cost); MCP calls nest as tools named after the function.

After a few turns, open **Traces** for individual requests and **Sessions** for the full conversation.

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

ShopAgent runs as an [MCP](https://modelcontextprotocol.io/) server that exposes catalog, cart, checkout, and memory tools: `filter_products`, `semantic_search`, `get_product`, `check_stock`, `add_to_cart`, `calculate_cart_total`, `checkout`, `save_shopper_memory`. Cart and checkout call the FastAPI service.

The CLI agent connects to this server automatically (one child process per session), lists tools via MCP, and invokes them with `call_tool`. You can also talk to the same server from the MCP Inspector.

Prerequisites are the same as the CLI: Compose DB up, catalog seeded, FastAPI running, and `.env` configured (`DATABASE_URL` required; `OPENAI_API_KEY` required for semantic search; `SHOPAGENT_API_KEY` required for cart/checkout). You also need `npx` on your `PATH` (Node.js) for the Inspector UI.

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
| Environment | one `KEY=VALUE` per line — at least `DATABASE_URL=...`, `OPENAI_API_KEY=...`, and `SHOPAGENT_API_KEY=...` (same values as `.env`) |
| Working directory | absolute path to the repo root, e.g. `/path/to/shop-agent` |

After **Add**, connect to the server, open **Tools**, and try `filter_products` (`category=Running`), then `add_to_cart` / `calculate_cart_total`.
