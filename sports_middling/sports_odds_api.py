"""Optional adapters for sportsbook-style odds APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from sports_middling.middling import (
    BetLeg,
    BetSide,
    american_to_decimal,
    balanced_stakes,
    build_middle_analysis,
)


THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
_LAST_API_USAGE: "ApiUsage | None" = None


class SportsOddsApiError(RuntimeError):
    """Raised when a sports odds API request or parse step fails."""


@dataclass(frozen=True)
class ApiUsage:
    """Usage metadata returned in The Odds API response headers."""

    requests_used: int | None
    requests_remaining: int | None


@dataclass(frozen=True)
class SportsEvent:
    """One event returned by an odds provider."""

    event_id: str
    sport_title: str
    commence_time: str
    home_team: str
    away_team: str

    @property
    def label(self) -> str:
        return f"{self.away_team} at {self.home_team} ({self.commence_time})"


@dataclass(frozen=True)
class SportsLeague:
    """One sport or league available from an odds provider."""

    key: str
    group: str
    title: str
    description: str
    active: bool
    has_outrights: bool

    @property
    def label(self) -> str:
        return f"{self.group} - {self.title}"


@dataclass(frozen=True)
class PropQuote:
    """One over/under quote for a player or game prop."""

    bookmaker: str
    market_key: str
    participant: str
    side: BetSide
    line: float
    american_odds: float
    event_id: str = ""
    event_label: str = ""
    commence_time: str = ""

    @property
    def decimal_odds(self) -> float:
        return american_to_decimal(self.american_odds)


@dataclass(frozen=True)
class MiddleCandidate:
    """Potential middle created by an over quote and an under quote."""

    event_id: str
    event_label: str
    commence_time: str
    participant: str
    market_key: str
    over_book: str
    under_book: str
    over_line: float
    under_line: float
    over_american_odds: float
    under_american_odds: float
    middle_width: float
    over_stake: float
    under_stake: float
    lower_tail_profit: float
    middle_profit: float
    upper_tail_profit: float


@dataclass(frozen=True)
class MarketOutcomeQuote:
    """One bookmaker quote for a generic market outcome."""

    event_id: str
    event_label: str
    commence_time: str
    bookmaker: str
    market_key: str
    group_key: str
    group_label: str
    outcome_key: str
    outcome_name: str
    american_odds: float
    point: float | None = None
    participant: str = ""

    @property
    def decimal_odds(self) -> float:
        return american_to_decimal(self.american_odds)


@dataclass(frozen=True)
class ArbitrageLeg:
    """Best available quote for one exhaustive market outcome."""

    outcome_name: str
    bookmaker: str
    american_odds: float
    decimal_odds: float
    stake: float
    payout: float


@dataclass(frozen=True)
class ArbitrageCandidate:
    """Line-shopping and arbitrage candidate across books."""

    event_id: str
    event_label: str
    commence_time: str
    market_key: str
    group_key: str
    group_label: str
    outcome_count: int
    implied_probability: float
    overround: float
    total_stake: float
    guaranteed_profit: float
    guaranteed_return: float
    legs: list[ArbitrageLeg]

    @property
    def signal(self) -> str:
        if self.guaranteed_profit > 0:
            return "TAKE"
        if self.implied_probability <= 1.03:
            return "WATCH"
        return "PASS"


@dataclass(frozen=True)
class OutrightLeg:
    """Best available price for one outright runner."""

    runner: str
    bookmaker: str
    american_odds: float
    decimal_odds: float
    stake: float
    payout: float


@dataclass(frozen=True)
class OutrightDutchCandidate:
    """Dutching portfolio for selected outright runners."""

    event_id: str
    event_label: str
    commence_time: str
    market_key: str
    group_key: str
    group_label: str
    runner_count: int
    implied_probability: float
    total_stake: float
    target_payout: float
    profit_if_hit: float
    return_if_hit: float
    legs: list[OutrightLeg]

    @property
    def signal(self) -> str:
        if self.implied_probability <= 0.35 and self.runner_count >= 2:
            return "TAKE"
        if self.implied_probability <= 0.60:
            return "WATCH"
        return "PASS"


def fetch_the_odds_api_sports(
    *,
    api_key: str,
    all_sports: bool = False,
) -> list[SportsLeague]:
    """Fetch available sports and leagues from The Odds API."""

    params: dict[str, Any] = {"apiKey": api_key}
    if all_sports:
        params["all"] = "true"
    payload = _get_json("/sports", params)
    if not isinstance(payload, list):
        raise SportsOddsApiError("Unexpected sports response from The Odds API.")
    return [
        SportsLeague(
            key=str(item.get("key", "")),
            group=str(item.get("group", "")),
            title=str(item.get("title", "")),
            description=str(item.get("description", "")),
            active=bool(item.get("active", False)),
            has_outrights=bool(item.get("has_outrights", False)),
        )
        for item in payload
        if item.get("key")
    ]


def fetch_the_odds_api_events(
    *,
    api_key: str,
    sport_key: str,
    days_from: int = 3,
) -> list[SportsEvent]:
    """Fetch upcoming events from The Odds API."""

    now = datetime.now(timezone.utc)
    commence_time_to = now + timedelta(days=days_from)
    payload = _get_json(
        f"/sports/{sport_key}/events",
        {
            "apiKey": api_key,
            "commenceTimeFrom": _format_utc_timestamp(now),
            "commenceTimeTo": _format_utc_timestamp(commence_time_to),
        },
    )
    if not isinstance(payload, list):
        raise SportsOddsApiError("Unexpected events response from The Odds API.")
    return [
        SportsEvent(
            event_id=str(item.get("id", "")),
            sport_title=str(item.get("sport_title", sport_key)),
            commence_time=str(item.get("commence_time", "")),
            home_team=str(item.get("home_team", "")),
            away_team=str(item.get("away_team", "")),
        )
        for item in payload
        if item.get("id")
    ]


def fetch_the_odds_api_event_odds(
    *,
    api_key: str,
    sport_key: str,
    event_id: str,
    regions: str,
    markets: str,
    odds_format: str = "american",
) -> dict[str, Any]:
    """Fetch odds for one event from The Odds API."""

    payload = _get_json(
        f"/sports/{sport_key}/events/{event_id}/odds",
        {
            "apiKey": api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        },
    )
    if not isinstance(payload, dict):
        raise SportsOddsApiError("Unexpected odds response from The Odds API.")
    return payload


def fetch_the_odds_api_event_markets(
    *,
    api_key: str,
    sport_key: str,
    event_id: str,
    regions: str,
) -> dict[str, Any]:
    """Fetch available market keys for one event from The Odds API."""

    payload = _get_json(
        f"/sports/{sport_key}/events/{event_id}/markets",
        {
            "apiKey": api_key,
            "regions": regions,
        },
    )
    if not isinstance(payload, dict):
        raise SportsOddsApiError("Unexpected event markets response from The Odds API.")
    return payload


def extract_prop_quotes(event_odds: dict[str, Any], market_key: str) -> list[PropQuote]:
    """Extract over/under quotes from one The Odds API event-odds payload."""

    quotes: list[PropQuote] = []
    event_id = str(event_odds.get("id", ""))
    commence_time = str(event_odds.get("commence_time", ""))
    event_label = _event_label(event_odds)
    for bookmaker in event_odds.get("bookmakers", []):
        bookmaker_title = str(bookmaker.get("title") or bookmaker.get("key") or "")
        for market in bookmaker.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                side = _parse_side(outcome.get("name"))
                point = outcome.get("point")
                price = outcome.get("price")
                if side is None or point is None or price is None:
                    continue
                participant = str(
                    outcome.get("description")
                    or outcome.get("participant")
                    or "Market"
                )
                quotes.append(
                    PropQuote(
                        bookmaker=bookmaker_title,
                        market_key=market_key,
                        participant=participant,
                        side=side,
                        line=float(point),
                        american_odds=float(price),
                        event_id=event_id,
                        event_label=event_label,
                        commence_time=commence_time,
                    )
                )
    return quotes


def extract_market_keys(event_markets: dict[str, Any]) -> list[str]:
    """Extract unique market keys from an event-markets payload."""

    market_keys = {
        str(market.get("key"))
        for bookmaker in event_markets.get("bookmakers", [])
        for market in bookmaker.get("markets", [])
        if market.get("key")
    }
    return sorted(market_keys)


def extract_market_outcome_quotes(
    event_odds: dict[str, Any],
    market_keys: list[str],
) -> list[MarketOutcomeQuote]:
    """Extract generic outcome quotes for arbitrage and line shopping."""

    selected_market_keys = set(market_keys)
    quotes: list[MarketOutcomeQuote] = []
    event_id = str(event_odds.get("id", ""))
    commence_time = str(event_odds.get("commence_time", ""))
    event_label = _event_label(event_odds)
    for bookmaker in event_odds.get("bookmakers", []):
        bookmaker_title = str(bookmaker.get("title") or bookmaker.get("key") or "")
        for market in bookmaker.get("markets", []):
            market_key = str(market.get("key", ""))
            if selected_market_keys and market_key not in selected_market_keys:
                continue
            for outcome in market.get("outcomes", []):
                price = outcome.get("price")
                if price is None:
                    continue
                point = _optional_float(outcome.get("point"))
                participant = str(
                    outcome.get("description")
                    or outcome.get("participant")
                    or ""
                )
                outcome_name = str(outcome.get("name") or participant or "Outcome")
                group_key, group_label, outcome_key = _generic_market_keys(
                    market_key=market_key,
                    event_id=event_id,
                    participant=participant,
                    outcome_name=outcome_name,
                    point=point,
                )
                quotes.append(
                    MarketOutcomeQuote(
                        event_id=event_id,
                        event_label=event_label,
                        commence_time=commence_time,
                        bookmaker=bookmaker_title,
                        market_key=market_key,
                        group_key=group_key,
                        group_label=group_label,
                        outcome_key=outcome_key,
                        outcome_name=outcome_name,
                        american_odds=float(price),
                        point=point,
                        participant=participant,
                    )
                )
    return quotes


def build_middle_candidates(
    quotes: list[PropQuote],
    *,
    total_stake: float = 100.0,
    require_different_books: bool = True,
) -> list[MiddleCandidate]:
    """Pair over and under quotes into possible middle candidates."""

    overs = [quote for quote in quotes if quote.side == BetSide.OVER]
    unders = [quote for quote in quotes if quote.side == BetSide.UNDER]
    candidates: list[MiddleCandidate] = []

    for over in overs:
        for under in unders:
            if over.participant != under.participant:
                continue
            if over.market_key != under.market_key:
                continue
            if require_different_books and over.bookmaker == under.bookmaker:
                continue
            if over.line >= under.line:
                continue

            over_stake, under_stake = balanced_stakes(
                total_stake=total_stake,
                over_odds_decimal=over.decimal_odds,
                under_odds_decimal=under.decimal_odds,
            )
            analysis = build_middle_analysis(
                over_leg=BetLeg(
                    side=BetSide.OVER,
                    line=over.line,
                    odds_decimal=over.decimal_odds,
                    stake=over_stake,
                    book=over.bookmaker,
                ),
                under_leg=BetLeg(
                    side=BetSide.UNDER,
                    line=under.line,
                    odds_decimal=under.decimal_odds,
                    stake=under_stake,
                    book=under.bookmaker,
                ),
                min_outcome=max(0.0, over.line - 5.0),
                max_outcome=under.line + 5.0,
                step=1.0,
            )
            candidates.append(
                MiddleCandidate(
                    event_id=over.event_id,
                    event_label=over.event_label,
                    commence_time=over.commence_time,
                    participant=over.participant,
                    market_key=over.market_key,
                    over_book=over.bookmaker,
                    under_book=under.bookmaker,
                    over_line=over.line,
                    under_line=under.line,
                    over_american_odds=over.american_odds,
                    under_american_odds=under.american_odds,
                    middle_width=analysis.middle_width,
                    over_stake=over_stake,
                    under_stake=under_stake,
                    lower_tail_profit=analysis.lower_tail_profit,
                    middle_profit=analysis.middle_profit,
                    upper_tail_profit=analysis.upper_tail_profit,
                )
            )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.middle_width,
            candidate.middle_profit,
            candidate.lower_tail_profit + candidate.upper_tail_profit,
        ),
        reverse=True,
    )


def build_arbitrage_candidates(
    quotes: list[MarketOutcomeQuote],
    *,
    total_stake: float = 100.0,
    max_implied_probability: float = 1.10,
) -> list[ArbitrageCandidate]:
    """Build best-price market candidates from generic outcome quotes."""

    groups: dict[str, list[MarketOutcomeQuote]] = {}
    for quote in quotes:
        groups.setdefault(quote.group_key, []).append(quote)

    candidates: list[ArbitrageCandidate] = []
    for group_quotes in groups.values():
        best_by_outcome = _best_quotes_by_outcome(group_quotes)
        if len(best_by_outcome) < 2:
            continue
        implied_probability = sum(
            1.0 / quote.decimal_odds
            for quote in best_by_outcome.values()
        )
        if implied_probability > max_implied_probability:
            continue

        payout = total_stake / implied_probability
        legs = [
            ArbitrageLeg(
                outcome_name=quote.outcome_name,
                bookmaker=quote.bookmaker,
                american_odds=quote.american_odds,
                decimal_odds=quote.decimal_odds,
                stake=payout / quote.decimal_odds,
                payout=payout,
            )
            for quote in best_by_outcome.values()
        ]
        reference_quote = group_quotes[0]
        guaranteed_profit = payout - total_stake
        candidates.append(
            ArbitrageCandidate(
                event_id=reference_quote.event_id,
                event_label=reference_quote.event_label,
                commence_time=reference_quote.commence_time,
                market_key=reference_quote.market_key,
                group_key=reference_quote.group_key,
                group_label=reference_quote.group_label,
                outcome_count=len(legs),
                implied_probability=implied_probability,
                overround=implied_probability - 1.0,
                total_stake=total_stake,
                guaranteed_profit=guaranteed_profit,
                guaranteed_return=guaranteed_profit / total_stake,
                legs=sorted(legs, key=lambda leg: leg.outcome_name),
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.guaranteed_profit,
            -candidate.implied_probability,
        ),
        reverse=True,
    )


def build_outright_dutch_candidates(
    quotes: list[MarketOutcomeQuote],
    *,
    total_stake: float = 100.0,
    max_runners: int = 5,
    max_implied_probability: float = 0.70,
) -> list[OutrightDutchCandidate]:
    """Build dutching portfolios from outright runner prices."""

    groups: dict[str, list[MarketOutcomeQuote]] = {}
    for quote in quotes:
        if quote.market_key not in {"outrights", "outrights_lay"}:
            continue
        groups.setdefault(quote.group_key, []).append(quote)

    candidates: list[OutrightDutchCandidate] = []
    for group_quotes in groups.values():
        best_by_runner = _best_quotes_by_outcome(group_quotes)
        ranked_quotes = sorted(
            best_by_runner.values(),
            key=lambda quote: quote.decimal_odds,
            reverse=True,
        )
        selected_quotes = ranked_quotes[:max(max_runners, 1)]
        if len(selected_quotes) < 2:
            continue
        implied_probability = sum(1.0 / quote.decimal_odds for quote in selected_quotes)
        if implied_probability > max_implied_probability:
            continue
        target_payout = total_stake / implied_probability
        legs = [
            OutrightLeg(
                runner=quote.outcome_name,
                bookmaker=quote.bookmaker,
                american_odds=quote.american_odds,
                decimal_odds=quote.decimal_odds,
                stake=target_payout / quote.decimal_odds,
                payout=target_payout,
            )
            for quote in selected_quotes
        ]
        reference_quote = group_quotes[0]
        profit_if_hit = target_payout - total_stake
        candidates.append(
            OutrightDutchCandidate(
                event_id=reference_quote.event_id,
                event_label=reference_quote.event_label,
                commence_time=reference_quote.commence_time,
                market_key=reference_quote.market_key,
                group_key=reference_quote.group_key,
                group_label=reference_quote.group_label,
                runner_count=len(legs),
                implied_probability=implied_probability,
                total_stake=total_stake,
                target_payout=target_payout,
                profit_if_hit=profit_if_hit,
                return_if_hit=profit_if_hit / total_stake,
                legs=legs,
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.return_if_hit,
            -candidate.implied_probability,
        ),
        reverse=True,
    )


def get_last_api_usage() -> ApiUsage | None:
    """Return the most recent usage headers seen from The Odds API."""

    return _LAST_API_USAGE


def _get_json(path: str, params: dict[str, Any]) -> Any:
    api_key = str(params.get("apiKey", "")).strip()
    if not api_key:
        raise SportsOddsApiError("An API key is required.")

    url = f"{THE_ODDS_API_BASE_URL}{path}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=20) as response:
            _capture_usage_headers(response.headers)
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        _capture_usage_headers(error.headers)
        detail = error.read().decode("utf-8", errors="replace")
        raise SportsOddsApiError(
            f"The Odds API returned HTTP {error.code}: {detail}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise SportsOddsApiError(f"The Odds API request failed: {error}") from error
    except json.JSONDecodeError as error:
        raise SportsOddsApiError("The Odds API returned invalid JSON.") from error


def _capture_usage_headers(headers) -> None:
    global _LAST_API_USAGE
    _LAST_API_USAGE = ApiUsage(
        requests_used=_header_int(headers, "x-requests-used"),
        requests_remaining=_header_int(headers, "x-requests-remaining"),
    )


def _header_int(headers, name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_side(value: Any) -> BetSide | None:
    normalized = str(value or "").strip().lower()
    if normalized == "over":
        return BetSide.OVER
    if normalized == "under":
        return BetSide.UNDER
    return None


def _event_label(event_odds: dict[str, Any]) -> str:
    away_team = str(event_odds.get("away_team") or "").strip()
    home_team = str(event_odds.get("home_team") or "").strip()
    if away_team and home_team:
        return f"{away_team} at {home_team}"
    return str(event_odds.get("sport_title") or "Event")


def _generic_market_keys(
    *,
    market_key: str,
    event_id: str,
    participant: str,
    outcome_name: str,
    point: float | None,
) -> tuple[str, str, str]:
    participant_key = _normalize_key(participant)
    point_key = "" if point is None else f"{point:g}"
    absolute_point_key = "" if point is None else f"{abs(point):g}"
    outcome_key = _normalize_key(outcome_name)

    if market_key in {"h2h", "h2h_lay", "outrights", "outrights_lay"}:
        group_key = f"{event_id}|{market_key}"
        group_label = market_key
    elif market_key == "spreads":
        group_key = f"{event_id}|{market_key}|{absolute_point_key}"
        group_label = f"{market_key} {absolute_point_key}"
    elif _is_over_under_market(market_key, outcome_name):
        group_key = f"{event_id}|{market_key}|{participant_key}|{point_key}"
        group_label = f"{participant or market_key} {point_key}".strip()
        outcome_key = outcome_key
    else:
        group_key = f"{event_id}|{market_key}|{participant_key}|{point_key}"
        group_label = " ".join(part for part in (participant, market_key, point_key) if part)

    return group_key, group_label, outcome_key


def _is_over_under_market(market_key: str, outcome_name: str) -> bool:
    return outcome_name.strip().lower() in {"over", "under"} or market_key == "totals"


def _best_quotes_by_outcome(
    quotes: list[MarketOutcomeQuote],
) -> dict[str, MarketOutcomeQuote]:
    best: dict[str, MarketOutcomeQuote] = {}
    for quote in quotes:
        existing = best.get(quote.outcome_key)
        if existing is None or quote.decimal_odds > existing.decimal_odds:
            best[quote.outcome_key] = quote
    return best


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _format_utc_timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
