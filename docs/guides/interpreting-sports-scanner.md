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
