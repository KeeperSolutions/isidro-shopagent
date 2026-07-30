# ShopAgent

A conversational shopping assistant that lets a user discover products, manage a cart, and check out — all through natural language.

This project was made as part of the training program on Agents, FastAPI and Stripe.

## Quick start

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

pip install -r requirements.txt
python -m shopagent
```

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |
| `OPENAI_MODEL` | Model name: `gpt-4.1-mini` (default), `gpt-4.1`, `gpt-4.1-nano`, `gpt-4o`, or `gpt-4o-mini` |
| `TEMPERATURE` | Sampling temperature (default `0.7`). |

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
