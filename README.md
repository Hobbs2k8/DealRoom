# DealRoom

A negotiating purchasing agent for small businesses. LA Hacks AI Hackathon 2026: Intuit QuickBooks (System One models) track and Fetch.ai ASI:One Agent Challenge.

A **buyer agent** reads a small business's QuickBooks accounts-payable data, finds a bill worth negotiating (price creep, a reliable payment history, a bill due near payroll), asks the owner in ASI:One whether to negotiate, haggles with a **supplier agent**, and asks the owner to approve the final deal. Nothing is agreed without owner approval.

> Status: step 4 of 5. The buyer speaks Fetch's Agent Chat Protocol over an Agentverse mailbox, so the owner can drive it from ASI:One. Jev comes next.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in seeds; API keys are optional
```

Python 3.13 works with uagents 0.26.1.

## Data

`data/company-001/` (Hearthloaf Bakeries) is committed so the demo runs without downloading anything. To get all 100 companies:

```bash
./scripts/fetch_data.sh
```

Each company lives at `data/company-XXX/rwm-v4/world-<id>/`, with one YAML file per entity type; field reference is in `SCHEMA.md` next to the YAML. Agents must never read a `hidden/` folder; the participant download does not include one, and `.gitignore` blocks it.

## Run the agents and chat from ASI:One

```bash
python run.py
```

On startup `run.py` prints an Agentverse inspector link for the buyer. **One time per seed:** open it while `run.py` is running, sign in, click **Connect**, and choose **Mailbox**. After that the buyer (`dealroom-buyer`) is reachable from ASI:One and from its Agentverse page. Until then the log says `Agent mailbox not found`, which is expected.

Chat commands (plain text): `scan`, `negotiate`, `passive` / `balanced` / `aggressive`, `status`, `approve`, `decline`. The buyer acknowledges every message, posts a short update each round, and asks for approval when the supplier accepts.

Test the chat locally without ASI:One (a fake owner agent sends the commands):

```bash
python -m scripts.chat_smoke_test
```

Other ways to run:

```bash
python run.py --auto                       # buyer scans and negotiates on startup (logs only)
python run.py --auto --mode aggressive
SUPPLIER_PERSONALITY=walker SUPPLIER_RNG_SEED=11 python run.py --auto
```

Both agents run in one Bureau on port 8000 (`BUREAU_PORT`). Supplier settings are optional env vars: `SUPPLIER_PERSONALITY`, `SUPPLIER_SEASON`, `SUPPLIER_RNG_SEED`. The "not enough funds to register on Almanac contract" warnings are expected: the agents register through the Almanac API instead, which is free.

## Run a negotiation in the terminal (no API keys needed)

```bash
python -m scripts.run_terminal_negotiation                       # random supplier
python -m scripts.run_terminal_negotiation --personality bluffer --mode aggressive --seed 7
python -m scripts.run_terminal_negotiation --cash-floor 100000   # prepaying would break the floor
```

Options: `--personality stubborn|desperate|bluffer|walker`, `--season busy|normal|slow`, `--mode passive|balanced|aggressive`, `--cash-floor`, `--seed`, `--company`. Each round prints the buyer's belief range, the top moves it considered, and both messages. The script writes `demo_state.json` (buyer) and `supplier_secret.json` (reveal).

## Layout

| File | What it does |
| --- | --- |
| `core/data.py` | Loads a company's YAML; refuses `hidden/` |
| `core/scout.py` | Per-vendor stats (spend, on-time rate, price change, open bills near payroll), best opportunity, cash context |
| `core/offers.py` | `Offer(price, quantity, pay_in_days)` |
| `core/belief.py` | Weighted samples of the supplier's floor; shrinks after each reply |
| `core/predictor.py` | `SupplierPredictor` interface, `HeuristicPredictor` (JevPredictor in step 5) |
| `core/search.py` | 8 candidate moves x 40 sampled suppliers x 3-round playouts, 2 s limit |
| `core/score.py` | Dollars saved, minus a huge penalty for breaking the cash floor |
| `core/negotiator.py` | Buyer session loop; writes `demo_state.json` every round |
| `core/writer.py` | Message text via Claude (`ANTHROPIC_API_KEY`), template fallback |
| `supplier/policy.py` | Rule-based supplier: secret floor, personality, season, prepay, terms. Imports nothing from `core/` |
| `scripts/run_terminal_negotiation.py` | Step 2 demo |
| `agents/messages.py` | `NegotiationStart`, `Offer`, `Accept`, `Reject` (uagents Models) |
| `agents/config.py` | Loads `.env` (seeds) and CA certificates |
| `agents/buyer.py` | Buyer uAgent; `BuyerController` handles scan / negotiate / mode / approve / decline |
| `agents/supplier.py` | Supplier uAgent around `supplier/policy.py` |
| `agents/chat.py` | ACP chat protocol: acknowledges every message, parses owner commands, sends updates |
| `agents/buyer_readme.md` | Agentverse profile text so ASI:One can discover the buyer |
| `scripts/chat_smoke_test.py` | Local chat test with a fake owner agent |
| `run.py` | Bureau with both agents |

## Data notes (company-001)

- Every bill is paid 1-3 days after its due date, so a strict on-time rate is 0% for every vendor. The scout counts a payment as on time if it lands within 3 days of due.
- Only product bills have item lines, so price creep exists only for the main supplier (Ironclad Larkspur Outfitters). Croissant trays rose 12.7% over the year, from $8.75 to $9.86 averaged.
- Cash is about $104k against about $5k of payroll per two weeks, so the cash floor only matters if you set it high (e.g. `--cash-floor 100000`).
- Messages default to `claude-opus-5-5` with low effort and a 4 s timeout; set `CLAUDE_MODEL` to change it. Refusals and errors fall back to templates.
