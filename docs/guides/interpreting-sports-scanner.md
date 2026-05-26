# Interpreting The Scanner

The app is a pricing and research tool. It is not betting advice.

## Key Terms

| Term | Meaning |
| --- | --- |
| Line shopping | Comparing books for the best line or odds on the same exposure. |
| Middle | Two bets that both win when the result lands inside a gap. |
| Tail loss | The loss outside the middle interval. |
| Middle profit | The profit if both legs win. |
| Break-even middle probability | Probability required for the middle to offset tail losses. |
| Model middle probability | The app's estimated chance of landing in the middle. |
| Model EV | Expected profit using the model probability. |

## Middle Math

```text
break_even_probability = tail_loss / (middle_profit + tail_loss)
expected_profit = p_middle * middle_profit + (1 - p_middle) * tail_profit
```

The app ranks candidates by comparing modeled middle probability with the
break-even probability implied by the payoff.

![Results table](../assets/sports-middling-live-results-table-wide.png)

## Before Trusting A Candidate

- Confirm both prices are still live.
- Confirm both books accept the intended stake.
- Confirm settlement and void rules match.
- Check whether the modeled distribution is realistic.
- Treat small edge as fragile after model error and execution risk.

## Saving Candidates

After a scan, use `Save displayed candidates to research log` to persist the
currently visible rows into a local SQLite database. This does not make another
API call and does not store the API key.

The Research Log tab lets you:

- Filter saved observations by type, signal, status, and text search.
- Export filtered observations to CSV.
- Add manual notes and a review status such as `Watched`, `Taken`, `Ignored`, or
  `Settled`.
- Keep the market snapshot so future backtesting work has a starting dataset.

## Current Research Limits

The scanner should be presented as a live research and payoff-analysis tool, not
as a fully backtested trading system.

| Limit | What it means |
| --- | --- |
| No historical odds database | The app does not yet store enough timestamped past prices to prove that similar middles have worked historically. Backtesting is therefore limited. |
| API prompts and credit caps | The app deliberately avoids constant polling so a small The Odds API quota is not burned accidentally. This is good quota discipline, but it limits continuous monitoring. |
| Limited CLV tracking | Closing-line value needs an entry price and a later closing price from the same market. Because the app only scans when prompted, CLV is a future upgrade rather than a current claim. |
| Saved-result workflow | The app now has a local SQLite Research Log for user-saved scans, but useful backtesting still needs repeated observations and final outcomes. |
| Execution simulation | The current app does not fully simulate rejected stakes, book limits, one-leg fills, stale prices, or latency. |
