# Sports Middling Lab

A Streamlit research app for finding and explaining sports betting market
opportunities: middles, line-shopping/arbitrage, and outright dutching
portfolios.

The app is built like a small sports trading desk tool. It separates payoff math
from model assumptions, guards API usage so a free The Odds API plan is not
burned accidentally, and lets a reviewer move from live market scan to payoff
chart to model notes.

![Sports middling live results](docs/assets/sports-middling-live-results-table-wide.png)

## Screenshots

| API prompt | Live scan controls | Results table |
| --- | --- | --- |
| ![API key prompt](docs/assets/sports-middling-api-prompt-wide.png) | ![Live scan controls](docs/assets/sports-middling-live-results-wide.png) | ![Live scan table](docs/assets/sports-middling-live-results-table-wide.png) |

| Payoff lab | Model notes |
| --- | --- |
| ![Payoff lab](docs/assets/sports-middling-payoff-lab-wide.png) | ![Model notes](docs/assets/sports-middling-model-notes-wide.png) |

## What Each Section Does

### Opportunity Scanner

The scanner connects to The Odds API only when the user explicitly arms live
calls and clicks a scan button. It can refresh the sports list, load events,
select sportsbook regions, choose market keys, estimate scan cost, and scan one
or more events under a single-digit credit cap.

The scanner supports three market modes:

- `Middles / Corridors`: finds over/under line gaps where both legs can win.
- `Arbitrage / Line Shopping`: keeps the best price for each exhaustive outcome
  and ranks guaranteed-return or low-overround books.
- `Outright / Dutching`: builds partial portfolios for golf, motorsport,
  awards, and tournament winner markets.

### Trade Signal

The `TAKE`, `WATCH`, and `PASS` labels are educational model signals. A `TAKE`
means the model middle probability clears the break-even middle probability by
the configured edge threshold and expected value is above the configured minimum.
It is not betting advice or an execution guarantee.

### Payoff Lab

The payoff lab turns two sportsbook legs into an options-style payoff diagram.
It shows middle outcomes, middle probability, expected PnL, expected ROI, max
loss, leg summary, outcome table, and distribution assumptions.

### Model Notes

The notes tab explains the intuition: a middle is a synthetic interval payoff;
line shopping searches for the best market expression of the same risk; EV
depends on the probability of landing inside the interval and the losses outside
it.

## Current Limitations

The app should be viewed as a live research and payoff-analysis tool, not a
fully backtested trading system.

- There is no historical odds database yet, so backtesting is limited.
- The API-prompt and credit-capped workflow protects a small The Odds API quota,
  but it also limits continuous market monitoring.
- Closing-line value tracking is limited because CLV needs timestamped entry
  prices and later closing prices from the same market.
- Saved scan storage, sport-specific models, execution simulation, and automated
  GitHub Actions checks are natural next upgrades.

## Guides

- [Getting started](docs/guides/getting-started.md)
- [The Odds API setup](docs/guides/the-odds-api.md)
- [Interpreting the scanner](docs/guides/interpreting-sports-scanner.md)
- [Screenshot gallery](docs/guides/screenshot-gallery.md)
- [project project guide](docs/guides/sports_betting_market_scanner_project_guide.pdf)

## Run Locally

```powershell
python -m pip install -e .
python -m streamlit run app.py
```

Manual payoff analysis works without credentials.

For live odds, copy the example secrets file and add your own key:

```powershell
New-Item -ItemType Directory -Force .streamlit
Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
notepad .streamlit/secrets.toml
python -m streamlit run app.py
```

Never commit `.streamlit/secrets.toml`.

## API Quota Safety

- No API call happens on page load or refresh.
- Live calls are disarmed by default.
- Every scan shows an estimated credit cost before execution.
- `Max/click` is capped from 1 to 9 credits.
- Auto-trim can reduce event count to stay under the cap.
- A reserve budget blocks scans that would consume the final quota.
- Live responses are cached briefly to reduce repeated accidental calls.

## Tests

```powershell
python -m unittest discover
```

## Disclaimer

This is an educational pricing and research tool. It does not account for
bookmaker limits, account restrictions, void rules, latency, taxes, model error,
or execution failure.
