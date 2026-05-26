# Getting Started

## Install

```powershell
python -m pip install -e .
```

## Run

```powershell
python -m streamlit run app.py
```

Manual mode works immediately. Live odds require The Odds API.

## Main Workflow

1. Open `Opportunity Scanner`.
2. Arm live API calls only when you are ready to spend credits.
3. Select sport, region, market keys, and market mode.
4. Load and scan a small number of events.
5. Review `TAKE`, `WATCH`, and `PASS` candidates.
6. Load a candidate into `Payoff Lab`.
7. Inspect the payoff, probability model, and outcome table.

![Live scan results](../assets/sports-middling-live-results-table-wide.png)

## Run Tests

```powershell
python -m unittest discover
```
