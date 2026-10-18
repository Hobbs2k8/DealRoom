# DealRoom

A negotiating purchasing agent for small businesses. LA Hacks AI Hackathon 2026: Intuit QuickBooks (System One models) track and Fetch.ai ASI:One Agent Challenge.

A **buyer agent** reads a small business's QuickBooks accounts-payable data, finds a bill worth negotiating (price creep, a reliable payment history, a bill due near payroll), asks the owner in ASI:One whether to negotiate, haggles with a **supplier agent**, and asks the owner to approve the final deal. Nothing is agreed without owner approval.

> Status: step 1 of 5 (data inspected, environment set up). Agents and brain code land in the next steps.

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

## Layout (planned)

```
agents/     buyer.py, supplier.py, messages.py   (uAgents)
core/       offers.py, belief.py, predictor.py, search.py, score.py, scout.py   (plain Python, no uagents)
scripts/    run_terminal_negotiation.py, fetch_data.sh
run.py      Bureau with both agents
```
