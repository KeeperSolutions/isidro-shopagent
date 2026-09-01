# Known limitations

ShopAgent is a training project. The main path works: search the catalog, add items to a cart, confirm, pay with Stripe Checkout, and mark the order `paid` from a webhook.

This file lists what is **not** built, or not safe for a real store.

---

## Database, inventory and concurrency

- Stock is reduced when a Stripe webhook marks an order `paid`, and restored on a full refund. There is **no reservation** when the order is created. Two API keys can each pass the stock check, pay, and both succeed. `adjust_inventory` refuses an update that would make `variants.inventory` negative, so the second decrement is skipped; both orders can still be `paid`. For demo purposes this is okay. A production store needs reservation or locking so you cannot sell more units than you have.

- The webhook commits the order as `paid` on the SQLModel session, then updates inventory on a **separate** psycopg connection. If that second update fails, the order stays `paid` and stock does not change. Reasoning behind this was to follow the course's database connection guideline that was in place before the API module. In a production environment it is critical to have consistency on the way we reach the database in order to perform database transactional operations safely.

- `python -m shopagent.seed` deletes and reloads `products` / `variants` from `data/catalog.json`. Although this allows for quick testing and re-testing of the catalog, it **resets live inventory** to the JSON file. Production database should always be separate from testing databases and seeds and fixtures like these should only run on a local/test environment.

## Cart and checkout

The HTTP API can add line items and create a Checkout Session. It cannot **remove** an item, **set quantity**, or **clear** the cart. The agent has no tools for those actions either. The goal of the demo was to achieve a working checkout while keeping the codebase as simple and readable as possible.

**Pending orders vs a live cart**

- After Stripe returns a checkout URL, the cart is retired (`checked_out`). If the shopper then adds more items, the agent creates a **new** cart. Checkout then creates another pending order. The previous pending order can still be paid.
- If the shopper **cancels** on Stripe, the cart is already retired. The agent can resume checkout from the pending order (`GET /orders`). There is no “cancel pending order” API, so that order stays `pending`.

**Prices**

- Cart and order lines store `unit_price` at add time. Stripe charges the catalog Price whose `lookup_key` is the SKU. Those amounts can differ after a catalog or Stripe sync.

**Checkout**

- `/checkout/success` and `/checkout/cancel` return JSON stubs. For a production environment it'd be best to set some actual pages that display the user in some way that the operation was successful. As the agentic conversation happens on a "per-turn" basis, the agent does not "react" to a webhook, and does not have context of the stubs. "pausing" user interaction with the agent while a checkout session is resolved is possible, but it would make the architecture too complex for the goal of the demo.

## Refunds

`POST /orders/{order_id}/refund` is HTTP-only. The agent cannot refund.

- The handler marks the order `refunded` as soon as Stripe accepts `refunds.create`. It does not wait for `charge.refunded`. This is fine for demo purposes.

- Refunds created in the Stripe Dashboard do not update the local order. The webhook handler only listens for `checkout.session.completed` and `payment_intent.succeeded`.

- Inventory is restored after the status commit, on a separate connection (same split as payment).

## Agent tools and conversation

MCP tools: `filter_products`, `semantic_search`, `get_product`, `check_stock`, `add_to_cart`, `calculate_cart_total`, `checkout`, `save_shopper_memory`.

Missing relative to the HTTP API: remove/update cart lines, list or fetch orders (the client uses `GET /orders` only inside checkout), refund.

Other agent limits:

- Conversation `input_items` grow for the whole CLI session (no truncation). For production there is a lot of evaluation here to determine how log the sessions get and what's a good truncation estimate, but without real user data we would be guestimating.

- Each model round reloads the system prompt with a live cart snapshot (`GET /cart`, and `GET /orders` when the cart is empty).

- Long-term memory is one file, `data/shopper_memory.json`. It is **not** keyed by API key. Evals and any local run share it. It is fine for a demo, but it production the API key should be mapped to a user profile database table in order to greet the user and save their preferences.

- `semantic_search` is cosine similarity only. It does not filter by price, category, or stock. Hybrid queries need a second tool call (`filter_products`).

- `products.embedding` has no ivfflat/hnsw index. That is fine for the current catalog (~30 products). If we want to scale (50k+ products) we'd need to index.

## Operations and packaging

- There are **no automated tests** and no CI workflow; it is out of the scope for this demo.

- Catalog schema lives in `db/init.sql`. Cart, order, and API-key tables are created by SQLModel `create_all` on API startup. For production we need to be consistent about the schemas.

- API keys are SHA-256 hashes with no name, revoke, or rotation. One key is one shopper identity and one active cart.
- There is no shopper web UI.
