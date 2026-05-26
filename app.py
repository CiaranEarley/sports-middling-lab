"""Streamlit interface for sports betting middling analysis."""

from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sports_middling.middling import (
    BetLeg,
    BetSide,
    MiddleAnalysis,
    american_to_decimal,
    balanced_stakes,
    build_middle_analysis,
    decimal_to_implied_probability,
    negative_binomial_probabilities,
    normal_probabilities,
    poisson_probabilities,
    summarize_expected_value,
)
from sports_middling.sports_odds_api import (
    SportsOddsApiError,
    build_arbitrage_candidates,
    build_middle_candidates,
    build_outright_dutch_candidates,
    extract_market_keys,
    extract_market_outcome_quotes,
    extract_prop_quotes,
    fetch_the_odds_api_event_markets,
    fetch_the_odds_api_event_odds,
    fetch_the_odds_api_events,
    fetch_the_odds_api_sports,
    get_last_api_usage,
)


PRESETS = {
    "NBA player points": {
        "market_label": "NBA player points",
        "over_book": "Book A",
        "under_book": "Book B",
        "over_line": 24.5,
        "under_line": 27.5,
        "over_american": -110,
        "under_american": -110,
        "outcome_step": 1.0,
        "min_outcome": 10.0,
        "max_outcome": 42.0,
        "distribution_model": "Normal",
        "distribution_mean": 26.0,
        "distribution_stdev": 6.0,
        "distribution_dispersion": 0.15,
    },
    "MLB pitcher strikeouts": {
        "market_label": "MLB pitcher strikeouts",
        "over_book": "Book A",
        "under_book": "Book B",
        "over_line": 5.5,
        "under_line": 7.5,
        "over_american": 105,
        "under_american": -120,
        "outcome_step": 1.0,
        "min_outcome": 0.0,
        "max_outcome": 14.0,
        "distribution_model": "Poisson",
        "distribution_mean": 6.4,
        "distribution_stdev": 2.5,
        "distribution_dispersion": 0.10,
    },
    "Soccer match goals": {
        "market_label": "Soccer match goals",
        "over_book": "Book A",
        "under_book": "Book B",
        "over_line": 2.5,
        "under_line": 3.5,
        "over_american": 115,
        "under_american": -130,
        "outcome_step": 1.0,
        "min_outcome": 0.0,
        "max_outcome": 8.0,
        "distribution_model": "Poisson",
        "distribution_mean": 2.8,
        "distribution_stdev": 1.6,
        "distribution_dispersion": 0.20,
    },
}

SPORT_OPTIONS = {
    "NBA": "basketball_nba",
    "MLB": "baseball_mlb",
    "English Premier League": "soccer_epl",
    "MLS": "soccer_usa_mls",
    "ATP French Open": "tennis_atp_french_open",
    "WTA French Open": "tennis_wta_french_open",
    "NFL": "americanfootball_nfl",
}

COMMON_MARKET_KEYS = {
    "basketball_nba": [
        "player_points",
        "player_rebounds",
        "player_assists",
        "player_threes",
        "player_blocks",
        "player_steals",
        "player_turnovers",
        "totals",
    ],
    "baseball_mlb": [
        "pitcher_strikeouts",
        "batter_total_bases",
        "batter_hits",
        "batter_runs",
        "batter_rbis",
        "totals",
    ],
    "soccer_epl": ["totals"],
    "soccer_usa_mls": ["totals"],
    "americanfootball_nfl": [
        "player_pass_tds",
        "player_pass_yds",
        "player_rush_yds",
        "player_receptions",
        "player_reception_yds",
        "totals",
    ],
    "tennis_atp_french_open": ["totals"],
    "tennis_wta_french_open": ["totals"],
}

MARKET_MODES = {
    "Middles / Corridors": "middles",
    "Arbitrage / Line Shopping": "arbitrage",
    "Outright / Dutching": "outrights",
}


def main() -> None:
    st.set_page_config(
        page_title="Sports Middling Lab",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _apply_styles()
    _initialize_state()

    st.title("Sports Middling Lab")
    st.caption(
        "Scan sportsbook lines for middling opportunities, then inspect the payoff like an options corridor."
    )

    scanner_tab, payoff_tab, notes_tab = st.tabs(
        ["Opportunity Scanner", "Payoff Lab", "Model Notes"]
    )
    with scanner_tab:
        _render_opportunity_scanner()
    with payoff_tab:
        _render_payoff_lab()
    with notes_tab:
        _render_model_notes(expanded=True)


def _initialize_state() -> None:
    defaults = {
        **PRESETS["NBA player points"],
        "odds_format": "American",
        "stake_mode": "Balanced total stake",
        "total_stake": 200.0,
        "over_stake": 100.0,
        "under_stake": 100.0,
        "over_decimal": american_to_decimal(-110),
        "under_decimal": american_to_decimal(-110),
        "api_calls_armed": False,
        "api_include_all_sports": True,
        "api_credit_budget": 500,
        "api_credit_reserve": 50,
        "api_max_credits_per_click": 5,
        "api_auto_trim_scans": True,
        "api_estimated_spent": 0,
        "api_last_used": None,
        "api_last_remaining": None,
        "candidate_model": "Poisson midpoint",
        "candidate_mean_shift": 0.0,
        "candidate_dispersion": 0.15,
        "candidate_take_edge_pct": 3.0,
        "candidate_watch_edge_pct": 0.0,
        "candidate_min_ev": 0.0,
        "outright_max_runners": 5,
        "outright_max_implied_pct": 70.0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_payoff_lab() -> None:
    controls_col, analytics_col = st.columns([0.85, 1.45])
    inputs = _manual_inputs(controls_col)

    analysis, probabilities, summary, payoff_frame = _build_manual_analysis(inputs)
    with analytics_col:
        if analysis.middle_width <= 0:
            st.warning("The over line must be below the under line to create a middle.")
        if summary.covered_probability < 0.98:
            st.info(
                f"The visible outcome grid covers {summary.covered_probability:.1%} of the selected distribution. "
                "Widen the min/max outcomes for a fuller EV estimate."
            )

        _render_metrics(analysis, summary)
        payoff_col, distribution_col = st.columns([1.2, 1.0])
        payoff_col.plotly_chart(
            _payoff_figure(analysis),
            use_container_width=True,
            key="manual_payoff_chart",
        )
        distribution_col.plotly_chart(
            _distribution_figure(analysis, probabilities),
            use_container_width=True,
            key="manual_distribution_chart",
        )
        _render_leg_summary(inputs["over_leg"], inputs["under_leg"])
        _render_payoff_table(payoff_frame)


def _build_manual_analysis(inputs: dict):
    analysis = build_middle_analysis(
        over_leg=inputs["over_leg"],
        under_leg=inputs["under_leg"],
        min_outcome=inputs["min_outcome"],
        max_outcome=inputs["max_outcome"],
        step=inputs["outcome_step"],
    )
    probabilities = _build_probabilities(
        model=inputs["distribution_model"],
        outcomes=analysis.outcomes,
        mean=inputs["distribution_mean"],
        stdev=inputs["distribution_stdev"],
        dispersion=inputs["distribution_dispersion"],
        step=inputs["outcome_step"],
    )
    summary = summarize_expected_value(analysis, probabilities)
    payoff_frame = _payoff_dataframe(analysis, probabilities)
    return analysis, probabilities, summary, payoff_frame


def _manual_inputs(container) -> dict:
    with container:
        st.header("Market")
        preset_name = st.selectbox("Preset", options=list(PRESETS), key="selected_preset")
        if st.button("Load preset", use_container_width=True):
            for key, value in PRESETS[preset_name].items():
                st.session_state[key] = value
            st.rerun()

        market_label = st.text_input("Market label", key="market_label")

        st.header("Lines")
        odds_format = st.radio(
            "Odds format",
            options=["American", "Decimal"],
            horizontal=True,
            key="odds_format",
        )
        over_book = st.text_input("Over book", key="over_book")
        over_line = st.number_input(
            "Over line",
            min_value=0.0,
            step=0.5,
            format="%.2f",
            key="over_line",
        )
        over_odds_decimal = _odds_input(
            label="Over odds",
            odds_format=odds_format,
            american_key="over_american",
            decimal_key="over_decimal",
        )

        under_book = st.text_input("Under book", key="under_book")
        under_line = st.number_input(
            "Under line",
            min_value=0.0,
            step=0.5,
            format="%.2f",
            key="under_line",
        )
        under_odds_decimal = _odds_input(
            label="Under odds",
            odds_format=odds_format,
            american_key="under_american",
            decimal_key="under_decimal",
        )

        st.header("Stakes")
        stake_mode = st.radio(
            "Stake mode",
            options=["Balanced total stake", "Manual stakes"],
            key="stake_mode",
        )
        if stake_mode == "Balanced total stake":
            total_stake = st.number_input(
                "Total stake",
                min_value=1.0,
                step=10.0,
                format="%.2f",
                key="total_stake",
            )
            over_stake, under_stake = balanced_stakes(
                total_stake=total_stake,
                over_odds_decimal=over_odds_decimal,
                under_odds_decimal=under_odds_decimal,
            )
            st.caption(
                f"Balanced stakes: {over_book or 'Over'} {over_stake:.2f}, "
                f"{under_book or 'Under'} {under_stake:.2f}"
            )
        else:
            over_stake = st.number_input(
                "Over stake",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                key="over_stake",
            )
            under_stake = st.number_input(
                "Under stake",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                key="under_stake",
            )

        st.header("Outcome Grid")
        min_outcome = st.number_input(
            "Minimum outcome",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key="min_outcome",
        )
        max_outcome = st.number_input(
            "Maximum outcome",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key="max_outcome",
        )
        outcome_step = st.number_input(
            "Outcome step",
            min_value=0.25,
            step=0.25,
            format="%.2f",
            key="outcome_step",
        )

        st.header("Distribution")
        distribution_model = st.selectbox(
            "Model",
            options=["Normal", "Poisson", "Negative binomial"],
            key="distribution_model",
        )
        distribution_mean = st.number_input(
            "Mean",
            min_value=0.01,
            step=0.5,
            format="%.2f",
            key="distribution_mean",
        )
        distribution_stdev = st.number_input(
            "Standard deviation",
            min_value=0.01,
            step=0.5,
            format="%.2f",
            key="distribution_stdev",
            disabled=distribution_model != "Normal",
        )
        distribution_dispersion = st.number_input(
            "Dispersion",
            min_value=0.01,
            step=0.01,
            format="%.2f",
            key="distribution_dispersion",
            disabled=distribution_model != "Negative binomial",
        )

    return {
        "market_label": market_label,
        "over_leg": BetLeg(
            side=BetSide.OVER,
            line=over_line,
            odds_decimal=over_odds_decimal,
            stake=over_stake,
            book=over_book,
        ),
        "under_leg": BetLeg(
            side=BetSide.UNDER,
            line=under_line,
            odds_decimal=under_odds_decimal,
            stake=under_stake,
            book=under_book,
        ),
        "min_outcome": min_outcome,
        "max_outcome": max_outcome,
        "outcome_step": outcome_step,
        "distribution_model": distribution_model,
        "distribution_mean": distribution_mean,
        "distribution_stdev": distribution_stdev,
        "distribution_dispersion": distribution_dispersion,
    }


def _odds_input(
    *,
    label: str,
    odds_format: str,
    american_key: str,
    decimal_key: str,
) -> float:
    if odds_format == "American":
        odds = st.number_input(label, step=5, key=american_key)
        return american_to_decimal(float(odds))
    return st.number_input(
        label,
        min_value=1.01,
        step=0.05,
        format="%.2f",
        key=decimal_key,
    )


def _build_probabilities(
    *,
    model: str,
    outcomes: list[float],
    mean: float,
    stdev: float,
    dispersion: float,
    step: float,
) -> dict[float, float]:
    if model == "Normal":
        return normal_probabilities(
            outcomes,
            mean=mean,
            stdev=stdev,
            step=step,
        )
    if model == "Poisson":
        return poisson_probabilities(outcomes, mean=mean)
    return negative_binomial_probabilities(
        outcomes,
        mean=mean,
        dispersion=dispersion,
    )


def _render_metrics(analysis: MiddleAnalysis, summary) -> None:
    middle_label = _format_middle_outcomes(analysis.middle_outcomes)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Middle", middle_label)
    metric_cols[1].metric("Middle probability", f"{summary.probability_middle:.2%}")
    metric_cols[2].metric("Expected PnL", f"{summary.expected_profit:,.2f}")
    metric_cols[3].metric("Expected ROI", f"{summary.expected_return_on_stake:.2%}")
    metric_cols[4].metric("Max loss", f"{analysis.max_loss:,.2f}")


def _render_leg_summary(over_leg: BetLeg, under_leg: BetLeg) -> None:
    st.subheader("Leg Summary")
    frame = pd.DataFrame(
        [
            {
                "Side": "Over",
                "Book": over_leg.book,
                "Line": over_leg.line,
                "Decimal odds": over_leg.odds_decimal,
                "American odds": _format_american_from_decimal(over_leg.odds_decimal),
                "Implied probability": decimal_to_implied_probability(over_leg.odds_decimal),
                "Stake": over_leg.stake,
            },
            {
                "Side": "Under",
                "Book": under_leg.book,
                "Line": under_leg.line,
                "Decimal odds": under_leg.odds_decimal,
                "American odds": _format_american_from_decimal(under_leg.odds_decimal),
                "Implied probability": decimal_to_implied_probability(under_leg.odds_decimal),
                "Stake": under_leg.stake,
            },
        ]
    )
    st.dataframe(
        frame.style.format(
            {
                "Line": "{:.2f}",
                "Decimal odds": "{:.3f}",
                "Implied probability": "{:.2%}",
                "Stake": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def _render_payoff_table(frame: pd.DataFrame) -> None:
    with st.expander("Outcome Table", expanded=True):
        st.dataframe(
            frame.style.format(
                {
                    "Over PnL": "{:.2f}",
                    "Under PnL": "{:.2f}",
                    "Total PnL": "{:.2f}",
                    "Probability": "{:.3%}",
                    "Weighted PnL": "{:.3f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "Download CSV",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name="sports_middle_payoff.csv",
            mime="text/csv",
            use_container_width=True,
        )


def _render_opportunity_scanner() -> None:
    api_key = _api_key_input()
    st.subheader("Live Opportunity Scanner")
    _render_credit_guard(api_key)

    discover_cols = st.columns([1.2, 1.1, 1.4])
    discover_cols[0].checkbox(
        "Include out-of-season sports",
        key="api_include_all_sports",
        help="The sports list endpoint is free. Enabling this can reveal golf, motorsport, futures, and out-of-season leagues.",
    )
    if discover_cols[1].button("Refresh available sports", use_container_width=True):
        if not api_key:
            st.warning("Add an API key before loading the live sports list.")
        else:
            try:
                st.session_state["api_sports"] = _cached_fetch_sports(
                    api_key=api_key,
                    all_sports=bool(st.session_state.get("api_include_all_sports", True)),
                )
                _record_api_call(0)
                st.success(f"Loaded {len(st.session_state['api_sports'])} sport key(s).")
            except SportsOddsApiError as error:
                st.warning(str(error))
    discover_cols[2].caption(
        "Sports/events discovery does not spend usage credits. Odds scans and event-market refreshes do."
    )

    top_cols = st.columns([1.0, 0.9, 0.9, 0.9])
    sport_options = _sport_options()
    current_sport = st.session_state.get("api_sport_choice", "NBA")
    if current_sport not in sport_options:
        st.session_state["api_sport_choice"] = list(sport_options)[0]
        current_sport = st.session_state["api_sport_choice"]
    sport_index = list(sport_options).index(current_sport)
    sport_label = top_cols[0].selectbox(
        "Sport",
        options=list(sport_options),
        index=sport_index,
        key="api_sport_choice",
    )
    sport_key = sport_options[sport_label]
    regions_selected = top_cols[1].multiselect(
        "Regions",
        options=["us", "us2", "uk", "eu", "au"],
        default=["us"],
        key="api_regions",
    )
    days_from = top_cols[2].number_input(
        "Days",
        min_value=1,
        max_value=7,
        value=3,
        step=1,
        key="api_days_from",
    )
    max_events_to_scan = top_cols[3].number_input(
        "Events",
        min_value=1,
        max_value=25,
        value=5,
        step=1,
        key="api_max_events",
    )
    regions = ",".join(regions_selected)

    market_cols = st.columns([1.4, 1.0])
    available_market_keys = st.session_state.get("available_market_keys", [])
    common_market_keys = COMMON_MARKET_KEYS.get(sport_key, [])
    market_options = sorted(set(common_market_keys) | set(available_market_keys))
    default_market_keys = [key for key in common_market_keys[:3] if key in market_options]
    market_keys = market_cols[0].multiselect(
        "Market keys",
        options=market_options,
        default=default_market_keys,
        help="Refresh event markets after loading events to discover keys currently offered for that event.",
        key=f"api_market_keys_{sport_key}",
    )
    extra_market_keys = market_cols[1].text_input(
        "Extra market keys",
        placeholder="alternate_totals,player_points",
        help="Comma-separated The Odds API market keys.",
        key="api_extra_market_keys",
    )
    selected_market_keys = _combine_market_keys(market_keys, extra_market_keys)
    mode_label = st.segmented_control(
        "Market mode",
        options=list(MARKET_MODES),
        default=st.session_state.get("market_mode_label", "Middles / Corridors"),
        key="market_mode_label",
        help="Middles search over/under line gaps. Arbitrage searches best prices for exhaustive outcome sets.",
    )
    market_mode = MARKET_MODES[mode_label]
    if market_mode == "outrights":
        selected_market_keys = _ensure_outrights_market_keys(selected_market_keys)
        _render_outright_controls()
    else:
        _render_recommendation_controls()
    selected_scan_cost = _estimate_odds_request_cost(
        event_count=1,
        market_keys=selected_market_keys,
        regions=regions,
    )
    event_cap = _event_cap_for_selection(
        market_keys=selected_market_keys,
        regions=regions,
        include_load_event_request=False,
    )
    load_and_scan_event_cap = event_cap
    safe_loaded_event_count = _safe_event_count(
        requested_count=int(max_events_to_scan),
        available_count=len(st.session_state.get("sports_events", [])),
        market_keys=selected_market_keys,
        regions=regions,
        include_load_event_request=False,
    )
    safe_load_and_scan_event_count = _safe_event_count(
        requested_count=int(max_events_to_scan),
        available_count=int(max_events_to_scan),
        market_keys=selected_market_keys,
        regions=regions,
        include_load_event_request=False,
    )
    batch_scan_cost = _estimate_odds_request_cost(
        event_count=safe_loaded_event_count,
        market_keys=selected_market_keys,
        regions=regions,
    )
    load_and_scan_cost = _estimate_odds_request_cost(
        event_count=safe_load_and_scan_event_count,
        market_keys=selected_market_keys,
        regions=regions,
    )
    st.caption(
        "Estimated credits: "
        f"load events 0, selected event scan {selected_scan_cost}, "
        f"loaded-event scan {batch_scan_cost}, load and scan {load_and_scan_cost}. "
        f"Current cap allows {event_cap} event(s) for the selected markets and regions."
    )
    max_per_click = int(st.session_state.get("api_max_credits_per_click", 5))
    if selected_scan_cost > max_per_click:
        st.warning(
            "Current market/region selection costs more than your Max/click cap even for one event. "
            "Reduce selected market keys or regions to enable scans."
        )

    action_cols = st.columns(4)
    if action_cols[0].button("Load events", use_container_width=True):
        events = _load_events(
            api_key=api_key,
            sport_key=sport_key,
            sport_label=sport_label,
            days_from=int(days_from),
        )
        if events is not None:
            st.success(f"Loaded {len(events)} event(s) for {sport_label}.")

    events = st.session_state.get("sports_events", [])
    if action_cols[1].button("Load and scan", use_container_width=True):
        if safe_load_and_scan_event_count <= 0:
            st.warning(
                "Load and scan would not be able to scan even one event under the current Max/click cap. "
                "Reduce market keys/regions or raise the cap."
            )
        elif _can_make_api_call("Load and scan", load_and_scan_cost):
            events = _load_events(
                api_key=api_key,
                sport_key=sport_key,
                sport_label=sport_label,
                days_from=int(days_from),
            )
            if events is None:
                return
            load_and_scan_events = _events_for_capped_scan(
                events=events,
                requested_count=int(max_events_to_scan),
                market_keys=selected_market_keys,
                regions=regions,
                include_load_event_request=False,
            )
            if load_and_scan_events:
                _scan_live_events(
                    api_key=api_key,
                sport_key=sport_key,
                regions=regions,
                market_keys=selected_market_keys,
                market_mode=market_mode,
                events=load_and_scan_events,
                total_stake=float(st.session_state.get("total_stake", 100.0)),
            )
    if action_cols[2].button("Scan loaded events", use_container_width=True):
        loaded_scan_events = _events_for_capped_scan(
            events=events,
            requested_count=int(max_events_to_scan),
            market_keys=selected_market_keys,
            regions=regions,
            include_load_event_request=False,
        )
        _scan_live_events(
            api_key=api_key,
            sport_key=sport_key,
            regions=regions,
            market_keys=selected_market_keys,
            market_mode=market_mode,
            events=loaded_scan_events,
            total_stake=float(st.session_state.get("total_stake", 100.0)),
        )

    if events:
        event_index = st.selectbox(
            "Loaded events",
            options=list(range(len(events))),
            format_func=lambda index: events[index].label,
            key="api_event_index",
        )
        if action_cols[3].button("Refresh selected event markets", use_container_width=True):
            _load_event_markets(
                api_key=api_key,
                sport_key=sport_key,
                regions=regions,
                event_id=events[event_index].event_id,
            )
        selected_scan_col, _ = st.columns([0.35, 0.65])
        if selected_scan_col.button("Scan selected event", use_container_width=True):
            _scan_live_events(
                api_key=api_key,
                sport_key=sport_key,
                regions=regions,
                market_keys=selected_market_keys,
                market_mode=market_mode,
                events=[events[event_index]],
                total_stake=float(st.session_state.get("total_stake", 100.0)),
            )

    if available_market_keys:
        st.caption(
            "Available markets for inspected event: "
            + ", ".join(available_market_keys[:24])
            + ("..." if len(available_market_keys) > 24 else "")
        )

    _render_scan_summary()
    _render_candidate_browser()


def _sport_options() -> dict[str, str]:
    options = dict(SPORT_OPTIONS)
    for sport in st.session_state.get("api_sports", []):
        label = sport.label if sport.group else sport.title
        if sport.key not in options.values() and label:
            options[label] = sport.key
    return options


def _render_recommendation_controls() -> None:
    st.subheader("Trade Signal")
    model_cols = st.columns([1.0, 0.8, 0.8, 0.8, 0.8])
    model_cols[0].selectbox(
        "Model",
        options=["Poisson midpoint", "Negative binomial midpoint", "Normal midpoint"],
        key="candidate_model",
        help="Fast dev-stage model. It centers the distribution on the middle interval and tests whether the middle is rich enough versus break-even.",
    )
    model_cols[1].number_input(
        "Mean shift",
        value=float(st.session_state.get("candidate_mean_shift", 0.0)),
        step=0.25,
        format="%.2f",
        key="candidate_mean_shift",
        help="Move the model mean away from the middle midpoint. Useful when you have a player-specific lean.",
    )
    model_cols[2].number_input(
        "Dispersion",
        min_value=0.01,
        value=float(st.session_state.get("candidate_dispersion", 0.15)),
        step=0.01,
        format="%.2f",
        key="candidate_dispersion",
        help="Used only for the negative-binomial model.",
    )
    model_cols[3].number_input(
        "Take edge %",
        min_value=0.0,
        value=float(st.session_state.get("candidate_take_edge_pct", 3.0)),
        step=0.5,
        format="%.1f",
        key="candidate_take_edge_pct",
        help="Minimum model probability edge over break-even required for TAKE.",
    )
    model_cols[4].number_input(
        "Min EV",
        value=float(st.session_state.get("candidate_min_ev", 0.0)),
        step=5.0,
        format="%.2f",
        key="candidate_min_ev",
        help="Minimum model EV required for TAKE.",
    )


def _render_outright_controls() -> None:
    st.subheader("Outright Dutching")
    control_cols = st.columns([0.8, 0.8, 1.4])
    control_cols[0].number_input(
        "Max runners",
        min_value=2,
        max_value=12,
        value=int(st.session_state.get("outright_max_runners", 5)),
        step=1,
        key="outright_max_runners",
        help="Build a dutching portfolio from the best-priced runners up to this count.",
    )
    control_cols[1].number_input(
        "Max implied %",
        min_value=5.0,
        max_value=100.0,
        value=float(st.session_state.get("outright_max_implied_pct", 70.0)),
        step=5.0,
        format="%.1f",
        key="outright_max_implied_pct",
        help="Drop portfolios whose selected runners are too expensive as a combined probability.",
    )
    control_cols[2].caption(
        "Use this for golf, motorsport, awards, and tournament winners. It is not risk-free unless the selected runners cover every possible winner."
    )


def _render_credit_guard(api_key: str) -> None:
    guard_cols = st.columns([1.0, 0.75, 0.75, 0.75, 0.75, 0.75])
    guard_cols[0].toggle(
        "Arm live API calls",
        key="api_calls_armed",
        help="When off, buttons cannot call The Odds API. Refreshing the app never calls the API.",
    )
    guard_cols[1].number_input(
        "Max/click",
        min_value=1,
        max_value=9,
        value=int(st.session_state.get("api_max_credits_per_click", 5)),
        step=1,
        key="api_max_credits_per_click",
        help="Hard cap for any single button click. Set to 1-9 while developing.",
    )
    guard_cols[2].toggle(
        "Auto-trim",
        key="api_auto_trim_scans",
        help="Trim batch scans to the largest event count that fits under Max/click.",
    )
    guard_cols[3].number_input(
        "Monthly budget",
        min_value=1,
        value=int(st.session_state.get("api_credit_budget", 500)),
        step=25,
        key="api_credit_budget",
    )
    guard_cols[4].number_input(
        "Reserve",
        min_value=0,
        value=int(st.session_state.get("api_credit_reserve", 50)),
        step=10,
        key="api_credit_reserve",
        help="Block new calls if the estimated remaining balance would fall below this.",
    )
    remaining = _estimated_remaining_credits()
    actual_remaining = st.session_state.get("api_last_remaining")
    guard_cols[5].metric(
        "Remaining",
        _format_credit_value(actual_remaining if actual_remaining is not None else remaining),
        help="Uses API response headers when available; otherwise uses the local estimate.",
    )
    st.caption(
        "Session estimate: "
        f"{_format_credit_value(st.session_state.get('api_estimated_spent', 0))} credit(s) from this app session."
    )
    if not api_key:
        st.warning("Add your API key in local Streamlit secrets or the temporary key box before arming calls.")
    elif not st.session_state.get("api_calls_armed", False):
        st.info("Live API calls are disarmed. You can refresh and use the app without spending credits.")


def _can_make_api_call(label: str, estimated_cost: int) -> bool:
    if not st.session_state.get("api_calls_armed", False):
        st.warning(f"{label} blocked. Turn on Arm live API calls first.")
        return False
    estimated_cost = max(int(estimated_cost), 0)
    max_per_click = int(st.session_state.get("api_max_credits_per_click", 5))
    if estimated_cost > max_per_click:
        st.error(
            f"{label} blocked. Estimated cost {estimated_cost} exceeds your "
            f"Max/click cap of {max_per_click}."
        )
        return False
    remaining = _estimated_remaining_credits()
    reserve = int(st.session_state.get("api_credit_reserve", 0))
    if remaining is not None and remaining - estimated_cost < reserve:
        st.error(
            f"{label} blocked. Estimated cost {estimated_cost} would leave "
            f"{remaining - estimated_cost} credits, below your reserve of {reserve}."
        )
        return False
    return True


def _record_api_call(estimated_cost: int) -> None:
    st.session_state["api_estimated_spent"] = int(
        st.session_state.get("api_estimated_spent", 0)
    ) + max(int(estimated_cost), 0)
    usage = get_last_api_usage()
    if usage is not None:
        st.session_state["api_last_used"] = usage.requests_used
        st.session_state["api_last_remaining"] = usage.requests_remaining


def _estimated_remaining_credits() -> int | None:
    actual_remaining = st.session_state.get("api_last_remaining")
    if actual_remaining is not None:
        return int(actual_remaining)
    budget = st.session_state.get("api_credit_budget")
    if budget is None:
        return None
    return int(budget) - int(st.session_state.get("api_estimated_spent", 0))


def _estimate_odds_request_cost(
    *,
    event_count: int,
    market_keys: list[str],
    regions: str,
) -> int:
    region_count = len([region for region in regions.split(",") if region.strip()])
    market_count = len([market_key for market_key in market_keys if market_key.strip()])
    if event_count <= 0 or region_count <= 0 or market_count <= 0:
        return 0
    return event_count * region_count * market_count


def _event_cap_for_selection(
    *,
    market_keys: list[str],
    regions: str,
    include_load_event_request: bool,
) -> int:
    max_per_click = int(st.session_state.get("api_max_credits_per_click", 5))
    available_for_odds = max_per_click - (1 if include_load_event_request else 0)
    per_event_cost = _estimate_odds_request_cost(
        event_count=1,
        market_keys=market_keys,
        regions=regions,
    )
    if available_for_odds <= 0 or per_event_cost <= 0:
        return 0
    return available_for_odds // per_event_cost


def _safe_event_count(
    *,
    requested_count: int,
    available_count: int,
    market_keys: list[str],
    regions: str,
    include_load_event_request: bool,
) -> int:
    requested_count = max(min(int(requested_count), int(available_count)), 0)
    if not st.session_state.get("api_auto_trim_scans", True):
        return requested_count
    event_cap = _event_cap_for_selection(
        market_keys=market_keys,
        regions=regions,
        include_load_event_request=include_load_event_request,
    )
    return min(requested_count, event_cap)


def _events_for_capped_scan(
    *,
    events,
    requested_count: int,
    market_keys: list[str],
    regions: str,
    include_load_event_request: bool,
):
    capped_count = _safe_event_count(
        requested_count=requested_count,
        available_count=len(events),
        market_keys=market_keys,
        regions=regions,
        include_load_event_request=include_load_event_request,
    )
    requested_available_count = max(min(int(requested_count), len(events)), 0)
    if (
        st.session_state.get("api_auto_trim_scans", True)
        and capped_count < requested_available_count
    ):
        st.info(
            f"Auto-trim limited this scan to {capped_count} event(s) so the click stays under "
            f"your Max/click cap of {st.session_state.get('api_max_credits_per_click', 5)}."
        )
    return events[:capped_count]


def _estimate_simple_request_cost(regions: str = "") -> int:
    region_count = len([region for region in regions.split(",") if region.strip()])
    return max(region_count, 1)


def _format_credit_value(value) -> str:
    if value is None:
        return "n/a"
    return f"{int(value):,}"


def _load_events(
    *,
    api_key: str,
    sport_key: str,
    sport_label: str,
    days_from: int,
):
    if not api_key:
        st.warning("Add an API key before loading events.")
        return None
    try:
        events = _cached_fetch_events(
            api_key=api_key,
            sport_key=sport_key,
            days_from=days_from,
        )
        _record_api_call(0)
    except SportsOddsApiError as error:
        st.warning(str(error))
        return None

    st.session_state["sports_events"] = events
    st.session_state["sports_event_sport_key"] = sport_key
    st.session_state["sports_event_sport_label"] = sport_label
    st.session_state["available_market_keys"] = []
    st.session_state["middle_candidates"] = []
    st.session_state["last_scan_summary"] = {}
    return events


def _load_event_markets(
    *,
    api_key: str,
    sport_key: str,
    regions: str,
    event_id: str,
) -> None:
    if not api_key or not regions:
        st.warning("Add an API key and at least one region before loading markets.")
        return
    estimated_cost = _estimate_simple_request_cost(regions)
    if not _can_make_api_call("Refresh selected event markets", estimated_cost):
        return
    try:
        event_markets = _cached_fetch_event_markets(
            api_key=api_key,
            sport_key=sport_key,
            event_id=event_id,
            regions=regions,
        )
        _record_api_call(estimated_cost)
    except SportsOddsApiError as error:
        st.warning(str(error))
        return
    st.session_state["available_market_keys"] = extract_market_keys(event_markets)
    if st.session_state["available_market_keys"]:
        st.success(f"Loaded {len(st.session_state['available_market_keys'])} market key(s).")
    else:
        st.info("No market keys were returned for that event and region.")


def _render_scan_summary() -> None:
    summary = st.session_state.get("last_scan_summary") or {}
    if not summary:
        return
    metric_cols = st.columns(5)
    metric_cols[0].metric("Events Scanned", summary.get("events", 0))
    metric_cols[1].metric("Markets", summary.get("markets", 0))
    metric_cols[2].metric("Quotes", summary.get("quotes", 0))
    metric_cols[3].metric("Middles", summary.get("candidates", 0))
    metric_cols[4].metric("Errors", summary.get("errors", 0))


def _render_candidate_browser() -> None:
    if st.session_state.get("last_result_type") == "outrights":
        _render_outright_browser()
        return
    if st.session_state.get("last_result_type") == "arbitrage":
        _render_arbitrage_browser()
        return

    candidates = st.session_state.get("middle_candidates", [])
    if not candidates:
        st.info("No opportunities loaded yet. Choose a sport, select market keys, then use Load and scan.")
        return

    st.subheader("Opportunities")
    filter_cols = st.columns([0.7, 0.7, 1.0])
    minimum_width = filter_cols[0].number_input(
        "Minimum width",
        min_value=0.0,
        value=0.0,
        step=0.5,
        key="candidate_min_width",
    )
    minimum_middle_pnl = filter_cols[1].number_input(
        "Minimum middle PnL",
        value=0.0,
        step=10.0,
        key="candidate_min_middle_pnl",
    )
    sort_by = filter_cols[2].selectbox(
        "Sort by",
        options=["Signal", "Model EV", "Edge", "Width", "Middle PnL", "Lower tail PnL", "Start"],
        key="candidate_sort_by",
    )
    filtered_candidates = [
        candidate
        for candidate in candidates
        if candidate.middle_width >= minimum_width
        and candidate.middle_profit >= minimum_middle_pnl
    ]
    filtered_candidates = _sort_candidates(filtered_candidates, sort_by)
    if not filtered_candidates:
        st.warning("No candidates match the current filters.")
        return

    candidate_frame = _candidate_dataframe(filtered_candidates)
    st.dataframe(
        candidate_frame.style.format(
            {
                "Break-even %": "{:.2%}",
                "Model middle %": "{:.2%}",
                "Edge": "{:.2%}",
                "Model EV": "{:.2f}",
                "Over line": "{:.2f}",
                "Under line": "{:.2f}",
                "Width": "{:.2f}",
                "Over odds": "{:.0f}",
                "Under odds": "{:.0f}",
                "Over stake": "{:.2f}",
                "Under stake": "{:.2f}",
                "Lower tail PnL": "{:.2f}",
                "Middle PnL": "{:.2f}",
                "Upper tail PnL": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download candidate scan",
        data=candidate_frame.to_csv(index=False).encode("utf-8"),
        file_name="sports_middle_candidates.csv",
        mime="text/csv",
        use_container_width=True,
    )

    selected_index = st.selectbox(
        "Browse opportunity",
        options=list(range(len(filtered_candidates))),
        format_func=lambda index: _candidate_label(filtered_candidates[index]),
        key="candidate_browser_index",
    )
    candidate = filtered_candidates[selected_index]
    _render_candidate_detail(candidate)


def _render_arbitrage_browser() -> None:
    candidates = st.session_state.get("arbitrage_candidates", [])
    if not candidates:
        st.info("No arbitrage or line-shopping opportunities loaded yet. Try H2H, totals, spreads, or outrights.")
        return

    st.subheader("Arbitrage / Line Shopping")
    filter_cols = st.columns([0.8, 0.8, 1.0])
    max_implied = filter_cols[0].number_input(
        "Max implied %",
        min_value=50.0,
        max_value=130.0,
        value=103.0,
        step=0.5,
        format="%.1f",
        key="arb_max_implied_pct",
    ) / 100.0
    only_take = filter_cols[1].checkbox("Only TAKE", value=False, key="arb_only_take")
    sort_by = filter_cols[2].selectbox(
        "Sort by",
        options=["Guaranteed Profit", "Implied Probability", "Start"],
        key="arb_sort_by",
    )
    filtered = [
        candidate
        for candidate in candidates
        if candidate.implied_probability <= max_implied
        and (not only_take or candidate.signal == "TAKE")
    ]
    filtered = _sort_arbitrage_candidates(filtered, sort_by)
    if not filtered:
        st.warning("No arbitrage candidates match the current filters.")
        return

    frame = _arbitrage_dataframe(filtered)
    st.dataframe(
        frame.style.format(
            {
                "Implied %": "{:.2%}",
                "Overround": "{:.2%}",
                "Guaranteed Profit": "{:.2f}",
                "Guaranteed Return": "{:.2%}",
                "Stake": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download arbitrage scan",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name="sports_arbitrage_candidates.csv",
        mime="text/csv",
        use_container_width=True,
    )
    selected_index = st.selectbox(
        "Browse arbitrage candidate",
        options=list(range(len(filtered))),
        format_func=lambda index: _arbitrage_label(filtered[index]),
        key="arbitrage_browser_index",
    )
    _render_arbitrage_detail(filtered[selected_index])


def _render_outright_browser() -> None:
    candidates = st.session_state.get("outright_candidates", [])
    if not candidates:
        st.info("No outright dutching portfolios loaded yet. Select Outright / Dutching and scan outrights.")
        return

    st.subheader("Outright / Dutching")
    filter_cols = st.columns([0.8, 0.8, 1.0])
    max_implied = filter_cols[0].number_input(
        "Max portfolio implied %",
        min_value=5.0,
        max_value=100.0,
        value=float(st.session_state.get("outright_max_implied_pct", 70.0)),
        step=5.0,
        format="%.1f",
        key="outright_filter_max_implied_pct",
    ) / 100.0
    minimum_return = filter_cols[1].number_input(
        "Min hit return %",
        value=0.0,
        step=5.0,
        format="%.1f",
        key="outright_min_return_pct",
    ) / 100.0
    sort_by = filter_cols[2].selectbox(
        "Sort by",
        options=["Return If Hit", "Implied Probability", "Runner Count"],
        key="outright_sort_by",
    )
    filtered = [
        candidate
        for candidate in candidates
        if candidate.implied_probability <= max_implied
        and candidate.return_if_hit >= minimum_return
    ]
    filtered = _sort_outright_candidates(filtered, sort_by)
    if not filtered:
        st.warning("No outright portfolios match the current filters.")
        return

    frame = _outright_dataframe(filtered)
    st.dataframe(
        frame.style.format(
            {
                "Portfolio implied": "{:.2%}",
                "Profit If Hit": "{:.2f}",
                "Return If Hit": "{:.2%}",
                "Stake": "{:.2f}",
                "Target Payout": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download outright portfolios",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name="sports_outright_dutching.csv",
        mime="text/csv",
        use_container_width=True,
    )
    selected_index = st.selectbox(
        "Browse outright portfolio",
        options=list(range(len(filtered))),
        format_func=lambda index: _outright_label(filtered[index]),
        key="outright_browser_index",
    )
    _render_outright_detail(filtered[selected_index])


def _sort_candidates(candidates, sort_by: str):
    if sort_by == "Signal":
        return sorted(
            candidates,
            key=lambda candidate: (
                _candidate_assessment(candidate)["rank"],
                _candidate_assessment(candidate)["expected_profit"],
            ),
            reverse=True,
        )
    if sort_by == "Model EV":
        return sorted(
            candidates,
            key=lambda candidate: _candidate_assessment(candidate)["expected_profit"],
            reverse=True,
        )
    if sort_by == "Edge":
        return sorted(
            candidates,
            key=lambda candidate: _candidate_assessment(candidate)["edge"],
            reverse=True,
        )
    if sort_by == "Middle PnL":
        return sorted(candidates, key=lambda candidate: candidate.middle_profit, reverse=True)
    if sort_by == "Lower tail PnL":
        return sorted(candidates, key=lambda candidate: candidate.lower_tail_profit, reverse=True)
    if sort_by == "Start":
        return sorted(candidates, key=lambda candidate: candidate.commence_time)
    return sorted(candidates, key=lambda candidate: candidate.middle_width, reverse=True)


def _sort_arbitrage_candidates(candidates, sort_by: str):
    if sort_by == "Implied Probability":
        return sorted(candidates, key=lambda candidate: candidate.implied_probability)
    if sort_by == "Start":
        return sorted(candidates, key=lambda candidate: candidate.commence_time)
    return sorted(candidates, key=lambda candidate: candidate.guaranteed_profit, reverse=True)


def _sort_outright_candidates(candidates, sort_by: str):
    if sort_by == "Implied Probability":
        return sorted(candidates, key=lambda candidate: candidate.implied_probability)
    if sort_by == "Runner Count":
        return sorted(candidates, key=lambda candidate: candidate.runner_count, reverse=True)
    return sorted(candidates, key=lambda candidate: candidate.return_if_hit, reverse=True)


def _candidate_label(candidate) -> str:
    return (
        f"{candidate.event_label} | {candidate.participant} | "
        f"O{candidate.over_line:g} {candidate.over_book} / "
        f"U{candidate.under_line:g} {candidate.under_book}"
    )


def _arbitrage_label(candidate) -> str:
    return (
        f"{candidate.signal} | {candidate.event_label} | "
        f"{candidate.group_label} | implied {candidate.implied_probability:.2%}"
    )


def _outright_label(candidate) -> str:
    return (
        f"{candidate.signal} | {candidate.event_label} | "
        f"{candidate.runner_count} runners | hit return {candidate.return_if_hit:.2%}"
    )


def _render_arbitrage_detail(candidate) -> None:
    detail_cols = st.columns([0.8, 1.2])
    with detail_cols[0]:
        st.subheader("Selected Market")
        st.metric("Signal", candidate.signal)
        st.write(f"**Event:** {candidate.event_label}")
        st.write(f"**Start:** {candidate.commence_time or 'n/a'}")
        st.write(f"**Market:** {candidate.market_key}")
        st.write(f"**Group:** {candidate.group_label}")
        metric_cols = st.columns(2)
        metric_cols[0].metric("Implied", f"{candidate.implied_probability:.2%}")
        metric_cols[1].metric("Overround", f"{candidate.overround:.2%}")
        metric_cols[0].metric("Profit", f"{candidate.guaranteed_profit:,.2f}")
        metric_cols[1].metric("Return", f"{candidate.guaranteed_return:.2%}")
    with detail_cols[1]:
        st.subheader("Execution Legs")
        st.dataframe(
            _arbitrage_legs_dataframe(candidate).style.format(
                {
                    "American odds": "{:.0f}",
                    "Decimal odds": "{:.3f}",
                    "Stake": "{:.2f}",
                    "Payout": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_outright_detail(candidate) -> None:
    detail_cols = st.columns([0.8, 1.2])
    with detail_cols[0]:
        st.subheader("Selected Portfolio")
        st.metric("Signal", candidate.signal)
        st.write(f"**Event:** {candidate.event_label}")
        st.write(f"**Start:** {candidate.commence_time or 'n/a'}")
        st.write(f"**Market:** {candidate.market_key}")
        metric_cols = st.columns(2)
        metric_cols[0].metric("Runners", candidate.runner_count)
        metric_cols[1].metric("Portfolio Implied", f"{candidate.implied_probability:.2%}")
        metric_cols[0].metric("Profit If Hit", f"{candidate.profit_if_hit:,.2f}")
        metric_cols[1].metric("Return If Hit", f"{candidate.return_if_hit:.2%}")
        st.caption(
            "This is a partial-coverage portfolio: it pays only if one of the selected runners wins."
        )
    with detail_cols[1]:
        st.subheader("Dutching Legs")
        st.dataframe(
            _outright_legs_dataframe(candidate).style.format(
                {
                    "American odds": "{:.0f}",
                    "Decimal odds": "{:.3f}",
                    "Stake": "{:.2f}",
                    "Target payout": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_candidate_detail(candidate) -> None:
    analysis = _candidate_analysis(candidate)
    assessment = _candidate_assessment(candidate)
    detail_cols = st.columns([0.9, 1.3])
    with detail_cols[0]:
        st.subheader("Selected Opportunity")
        st.metric("Signal", assessment["signal"])
        st.write(f"**Event:** {candidate.event_label}")
        st.write(f"**Start:** {candidate.commence_time or 'n/a'}")
        st.write(f"**Market:** {candidate.market_key}")
        st.write(f"**Participant:** {candidate.participant}")
        metric_cols = st.columns(2)
        metric_cols[0].metric("Model middle", f"{assessment['model_middle_probability']:.2%}")
        metric_cols[1].metric("Break-even", f"{assessment['break_even_probability']:.2%}")
        metric_cols[0].metric("Edge", f"{assessment['edge']:.2%}")
        metric_cols[1].metric("Model EV", f"{assessment['expected_profit']:,.2f}")
        metric_cols[0].metric("Middle PnL", f"{candidate.middle_profit:,.2f}")
        metric_cols[1].metric("Worst Tail PnL", f"{assessment['worst_tail_profit']:,.2f}")
        if st.button("Load into payoff lab", use_container_width=True):
            _apply_candidate_to_state(candidate, candidate.market_key)
            st.success("Loaded this opportunity into the Payoff Lab tab.")
    with detail_cols[1]:
        candidate_chart_key = (
            "candidate_payoff_chart_"
            f"{candidate.event_label}_{candidate.market_key}_{candidate.participant}_"
            f"{candidate.over_book}_{candidate.over_line}_{candidate.over_american_odds}_"
            f"{candidate.under_book}_{candidate.under_line}_{candidate.under_american_odds}"
        )
        st.plotly_chart(
            _payoff_figure(analysis),
            use_container_width=True,
            key=candidate_chart_key,
        )


def _candidate_analysis(candidate) -> MiddleAnalysis:
    return build_middle_analysis(
        over_leg=BetLeg(
            side=BetSide.OVER,
            line=candidate.over_line,
            odds_decimal=american_to_decimal(candidate.over_american_odds),
            stake=candidate.over_stake,
            book=candidate.over_book,
        ),
        under_leg=BetLeg(
            side=BetSide.UNDER,
            line=candidate.under_line,
            odds_decimal=american_to_decimal(candidate.under_american_odds),
            stake=candidate.under_stake,
            book=candidate.under_book,
        ),
        min_outcome=max(0.0, candidate.over_line - 6.0),
        max_outcome=candidate.under_line + 6.0,
        step=1.0,
    )


def _candidate_assessment(candidate) -> dict:
    analysis = _candidate_analysis(candidate)
    model_probability = _model_middle_probability(analysis)
    worst_tail_profit = min(candidate.lower_tail_profit, candidate.upper_tail_profit)
    worst_tail_loss = abs(min(worst_tail_profit, 0.0))
    break_even_probability = _break_even_middle_probability(
        middle_profit=candidate.middle_profit,
        tail_loss=worst_tail_loss,
    )
    expected_profit = (
        model_probability * candidate.middle_profit
        + (1.0 - model_probability) * worst_tail_profit
    )
    edge = model_probability - break_even_probability
    signal = _trade_signal(edge=edge, expected_profit=expected_profit)
    return {
        "signal": signal,
        "rank": {"TAKE": 3, "WATCH": 2, "PASS": 1}.get(signal, 0),
        "break_even_probability": break_even_probability,
        "model_middle_probability": model_probability,
        "edge": edge,
        "expected_profit": expected_profit,
        "worst_tail_profit": worst_tail_profit,
    }


def _model_middle_probability(analysis: MiddleAnalysis) -> float:
    if not analysis.middle_outcomes:
        return 0.0
    middle_mean = sum(analysis.middle_outcomes) / len(analysis.middle_outcomes)
    model_mean = max(
        middle_mean + float(st.session_state.get("candidate_mean_shift", 0.0)),
        0.01,
    )
    model_name = st.session_state.get("candidate_model", "Poisson midpoint")
    if model_name == "Negative binomial midpoint":
        probabilities = negative_binomial_probabilities(
            analysis.outcomes,
            mean=model_mean,
            dispersion=float(st.session_state.get("candidate_dispersion", 0.15)),
        )
    elif model_name == "Normal midpoint":
        probabilities = normal_probabilities(
            analysis.outcomes,
            mean=model_mean,
            stdev=max(model_mean ** 0.5, 0.75),
            step=1.0,
        )
    else:
        probabilities = poisson_probabilities(analysis.outcomes, mean=model_mean)
    return sum(probabilities.get(outcome, 0.0) for outcome in analysis.middle_outcomes)


def _break_even_middle_probability(*, middle_profit: float, tail_loss: float) -> float:
    if middle_profit <= 0:
        return 1.0
    denominator = middle_profit + tail_loss
    if denominator <= 0:
        return 1.0
    return tail_loss / denominator


def _trade_signal(*, edge: float, expected_profit: float) -> str:
    take_edge = float(st.session_state.get("candidate_take_edge_pct", 3.0)) / 100.0
    watch_edge = float(st.session_state.get("candidate_watch_edge_pct", 0.0)) / 100.0
    minimum_ev = float(st.session_state.get("candidate_min_ev", 0.0))
    if edge >= take_edge and expected_profit >= minimum_ev:
        return "TAKE"
    if edge > watch_edge:
        return "WATCH"
    return "PASS"


def _combine_market_keys(selected_keys: list[str], extra_keys: str) -> list[str]:
    market_keys = [key.strip() for key in selected_keys if key.strip()]
    market_keys.extend(
        key.strip()
        for key in extra_keys.split(",")
        if key.strip()
    )
    return list(dict.fromkeys(market_keys))


def _ensure_outrights_market_keys(market_keys: list[str]) -> list[str]:
    keys = [key for key in market_keys if key]
    if "outrights" not in keys:
        keys.insert(0, "outrights")
    return list(dict.fromkeys(keys))


def _scan_live_events(
    *,
    api_key: str,
    sport_key: str,
    regions: str,
    market_keys: list[str],
    market_mode: str,
    events,
    total_stake: float,
) -> None:
    if not api_key or not regions:
        st.warning("Add an API key and at least one region before scanning odds.")
        return
    if not market_keys:
        st.warning("Select at least one market key to scan.")
        return
    if not events:
        st.warning("Load events before scanning odds.")
        return

    estimated_cost = _estimate_odds_request_cost(
        event_count=len(events),
        market_keys=market_keys,
        regions=regions,
    )
    if not _can_make_api_call("Scan odds", estimated_cost):
        return

    middle_candidates = []
    arbitrage_candidates = []
    outright_candidates = []
    quote_count = 0
    errors = []
    markets = ",".join(market_keys)
    with st.spinner(f"Scanning {len(events)} event(s) across {len(market_keys)} market key(s)..."):
        for event in events:
            try:
                event_odds = _cached_fetch_event_odds(
                    api_key=api_key,
                    sport_key=sport_key,
                    event_id=event.event_id,
                    regions=regions,
                    markets=markets,
                )
                if market_mode == "outrights":
                    quotes = extract_market_outcome_quotes(event_odds, market_keys)
                    outright_candidates.extend(
                        build_outright_dutch_candidates(
                            quotes,
                            total_stake=total_stake,
                            max_runners=int(st.session_state.get("outright_max_runners", 5)),
                            max_implied_probability=float(
                                st.session_state.get("outright_max_implied_pct", 70.0)
                            )
                            / 100.0,
                        )
                    )
                elif market_mode == "arbitrage":
                    quotes = extract_market_outcome_quotes(event_odds, market_keys)
                    arbitrage_candidates.extend(
                        build_arbitrage_candidates(
                            quotes,
                            total_stake=total_stake,
                        )
                    )
                else:
                    quotes = []
                    for market_key in market_keys:
                        quotes.extend(extract_prop_quotes(event_odds, market_key))
                    middle_candidates.extend(
                        build_middle_candidates(
                            quotes,
                            total_stake=total_stake,
                        )
                    )
                quote_count += len(quotes)
                _record_api_call(
                    _estimate_odds_request_cost(
                        event_count=1,
                        market_keys=market_keys,
                        regions=regions,
                    )
                )
            except SportsOddsApiError as error:
                errors.append(f"{event.label}: {error}")

    if market_mode == "outrights":
        st.session_state["outright_candidates"] = sorted(
            outright_candidates,
            key=lambda candidate: candidate.return_if_hit,
            reverse=True,
        )
        st.session_state["arbitrage_candidates"] = []
        st.session_state["middle_candidates"] = []
        result_count = len(st.session_state["outright_candidates"])
        result_label = "outright dutching portfolio(s)"
    elif market_mode == "arbitrage":
        st.session_state["arbitrage_candidates"] = arbitrage_candidates
        st.session_state["middle_candidates"] = []
        st.session_state["outright_candidates"] = []
        result_count = len(arbitrage_candidates)
        result_label = "arbitrage/line-shopping candidate(s)"
    else:
        st.session_state["middle_candidates"] = middle_candidates
        st.session_state["arbitrage_candidates"] = []
        st.session_state["outright_candidates"] = []
        result_count = len(middle_candidates)
        result_label = "middle candidate(s)"
    st.session_state["last_result_type"] = market_mode
    st.session_state["last_scan_summary"] = {
        "events": len(events),
        "markets": len(market_keys),
        "quotes": quote_count,
        "candidates": result_count,
        "errors": len(errors),
    }
    if errors:
        st.warning("Some events failed to scan: " + " | ".join(errors[:3]))
    if result_count:
        st.success(
            f"Found {result_count} {result_label} from {quote_count} quote(s)."
        )
    else:
        st.info(
            f"Scanned {len(events)} event(s) and {quote_count} quote(s), but found no line middles."
        )


def _candidate_dataframe(candidates) -> pd.DataFrame:
    return pd.DataFrame(
        [
            _candidate_row(candidate)
            for candidate in candidates
        ]
    )


def _candidate_row(candidate) -> dict:
    assessment = _candidate_assessment(candidate)
    return {
        "Signal": assessment["signal"],
        "Break-even %": assessment["break_even_probability"],
        "Model middle %": assessment["model_middle_probability"],
        "Edge": assessment["edge"],
        "Model EV": assessment["expected_profit"],
        "Event": candidate.event_label,
        "Start": candidate.commence_time,
        "Market": candidate.market_key,
        "Participant": candidate.participant,
        "Over book": candidate.over_book,
        "Over line": candidate.over_line,
        "Over odds": candidate.over_american_odds,
        "Under book": candidate.under_book,
        "Under line": candidate.under_line,
        "Under odds": candidate.under_american_odds,
        "Width": candidate.middle_width,
        "Over stake": candidate.over_stake,
        "Under stake": candidate.under_stake,
        "Lower tail PnL": candidate.lower_tail_profit,
        "Middle PnL": candidate.middle_profit,
        "Upper tail PnL": candidate.upper_tail_profit,
    }


def _arbitrage_dataframe(candidates) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Signal": candidate.signal,
                "Event": candidate.event_label,
                "Start": candidate.commence_time,
                "Market": candidate.market_key,
                "Group": candidate.group_label,
                "Outcomes": candidate.outcome_count,
                "Implied %": candidate.implied_probability,
                "Overround": candidate.overround,
                "Guaranteed Profit": candidate.guaranteed_profit,
                "Guaranteed Return": candidate.guaranteed_return,
                "Stake": candidate.total_stake,
                "Best Legs": _format_arbitrage_legs(candidate),
            }
            for candidate in candidates
        ]
    )


def _arbitrage_legs_dataframe(candidate) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Outcome": leg.outcome_name,
                "Book": leg.bookmaker,
                "American odds": leg.american_odds,
                "Decimal odds": leg.decimal_odds,
                "Stake": leg.stake,
                "Payout": leg.payout,
            }
            for leg in candidate.legs
        ]
    )


def _outright_dataframe(candidates) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Signal": candidate.signal,
                "Event": candidate.event_label,
                "Start": candidate.commence_time,
                "Market": candidate.market_key,
                "Runners": candidate.runner_count,
                "Portfolio implied": candidate.implied_probability,
                "Stake": candidate.total_stake,
                "Target Payout": candidate.target_payout,
                "Profit If Hit": candidate.profit_if_hit,
                "Return If Hit": candidate.return_if_hit,
                "Legs": _format_outright_legs(candidate),
            }
            for candidate in candidates
        ]
    )


def _outright_legs_dataframe(candidate) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Runner": leg.runner,
                "Book": leg.bookmaker,
                "American odds": leg.american_odds,
                "Decimal odds": leg.decimal_odds,
                "Stake": leg.stake,
                "Target payout": leg.payout,
            }
            for leg in candidate.legs
        ]
    )


def _format_arbitrage_legs(candidate) -> str:
    return " | ".join(
        f"{leg.outcome_name}: {leg.bookmaker} {leg.american_odds:+.0f}"
        for leg in candidate.legs
    )


def _format_outright_legs(candidate) -> str:
    return " | ".join(
        f"{leg.runner}: {leg.bookmaker} {leg.american_odds:+.0f}"
        for leg in candidate.legs
    )


def _render_model_notes(*, expanded: bool = False) -> None:
    content = """
    - A middle is a synthetic interval payoff: the over wins above the lower line
      and the under wins below the higher line.
    - The live scanner looks for the same participant and market where one book's
      over line is below another book's under line.
    - Arbitrage / Line Shopping mode builds exhaustive outcome sets, keeps the
      best price for each outcome, and flags positive guaranteed-return books.
    - The TAKE/WATCH/PASS signal compares model middle probability against the
      break-even middle probability implied by the payoff.
    - The default dev-stage model is a midpoint Poisson model. It is useful for
      ranking candidates, not a substitute for player-specific projections.
    - The tail stakes can be balanced by matching over stake times over decimal
      odds to under stake times under decimal odds.
    - EV depends on the modeled probability of landing inside the interval and
      the tail loss or gain outside it.
    - The app is an educational pricing tool and does not account for limits,
      bet acceptance risk, account restrictions, taxes, latency, or execution.
    """
    if expanded:
        st.markdown(content)
        return
    with st.expander("Model Notes"):
        st.markdown(content)


def _payoff_dataframe(
    analysis: MiddleAnalysis,
    probabilities: dict[float, float],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Outcome": point.outcome,
                "State": point.state.title(),
                "Over PnL": point.over_profit,
                "Under PnL": point.under_profit,
                "Total PnL": point.total_profit,
                "Probability": probabilities.get(point.outcome, 0.0),
                "Weighted PnL": probabilities.get(point.outcome, 0.0) * point.total_profit,
            }
            for point in analysis.payoff_points
        ]
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_fetch_events(
    *,
    api_key: str,
    sport_key: str,
    days_from: int,
):
    return fetch_the_odds_api_events(
        api_key=api_key,
        sport_key=sport_key,
        days_from=days_from,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_fetch_sports(*, api_key: str, all_sports: bool):
    return fetch_the_odds_api_sports(api_key=api_key, all_sports=all_sports)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_fetch_event_odds(
    *,
    api_key: str,
    sport_key: str,
    event_id: str,
    regions: str,
    markets: str,
):
    return fetch_the_odds_api_event_odds(
        api_key=api_key,
        sport_key=sport_key,
        event_id=event_id,
        regions=regions,
        markets=markets,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _cached_fetch_event_markets(
    *,
    api_key: str,
    sport_key: str,
    event_id: str,
    regions: str,
):
    return fetch_the_odds_api_event_markets(
        api_key=api_key,
        sport_key=sport_key,
        event_id=event_id,
        regions=regions,
    )


def _payoff_figure(analysis: MiddleAnalysis) -> go.Figure:
    frame = _payoff_dataframe(analysis, {point.outcome: 0.0 for point in analysis.payoff_points})
    figure = go.Figure()
    if analysis.middle_width > 0:
        figure.add_vrect(
            x0=analysis.over_leg.line,
            x1=analysis.under_leg.line,
            fillcolor="#bbf7d0",
            opacity=0.35,
            line_width=0,
        )
    figure.add_trace(
        go.Scatter(
            x=frame["Outcome"],
            y=frame["Total PnL"],
            mode="lines+markers",
            name="Total PnL",
            line={"color": "#0f766e", "width": 3},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=frame["Outcome"],
            y=frame["Over PnL"],
            mode="lines",
            name="Over leg",
            line={"color": "#2563eb", "dash": "dash"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=frame["Outcome"],
            y=frame["Under PnL"],
            mode="lines",
            name="Under leg",
            line={"color": "#dc2626", "dash": "dash"},
        )
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#64748b")
    figure.update_layout(
        title="Payoff by Outcome",
        xaxis_title="Settled outcome",
        yaxis_title="Net profit",
        height=500,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def _distribution_figure(
    analysis: MiddleAnalysis,
    probabilities: dict[float, float],
) -> go.Figure:
    colors = {
        "middle": "#16a34a",
        "lower tail": "#dc2626",
        "upper tail": "#dc2626",
        "push": "#64748b",
        "dead zone": "#7f1d1d",
    }
    marker_colors = [
        colors.get(point.state, "#334155")
        for point in analysis.payoff_points
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=analysis.outcomes,
            y=[probabilities.get(point.outcome, 0.0) for point in analysis.payoff_points],
            marker_color=marker_colors,
            name="Probability",
            customdata=[
                [point.state.title(), point.total_profit]
                for point in analysis.payoff_points
            ],
            hovertemplate=(
                "Outcome: %{x}<br>"
                "Probability: %{y:.3%}<br>"
                "State: %{customdata[0]}<br>"
                "PnL: %{customdata[1]:.2f}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title="Outcome Distribution",
        xaxis_title="Settled outcome",
        yaxis_title="Probability",
        height=500,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def _format_middle_outcomes(outcomes: list[float]) -> str:
    if not outcomes:
        return "None"
    if len(outcomes) <= 4:
        return ", ".join(f"{outcome:g}" for outcome in outcomes)
    return f"{outcomes[0]:g} to {outcomes[-1]:g}"


def _format_american_from_decimal(decimal_odds: float) -> str:
    if decimal_odds >= 2.0:
        return f"+{round((decimal_odds - 1.0) * 100.0):.0f}"
    return f"{round(-100.0 / (decimal_odds - 1.0)):.0f}"


def _api_key_input() -> str:
    configured_key = _configured_api_key()
    if configured_key:
        st.success("Server-side The Odds API key loaded. Visitors do not need to enter a key.")
        return configured_key

    st.info(
        "No server-side The Odds API key is configured. Manual analysis still works; "
        "live odds require a deployment secret or local environment variable."
    )
    return st.text_input(
        "Temporary The Odds API key",
        type="password",
        help="Used only for this local session. Do not commit API keys to the repo.",
    ).strip()


def _configured_api_key() -> str:
    try:
        secret_value = st.secrets.get("THE_ODDS_API_KEY", "")
    except Exception:
        secret_value = ""
    return str(secret_value or os.getenv("THE_ODDS_API_KEY", ""))


def _apply_candidate_to_state(candidate, market_key: str) -> None:
    model_mean = max((float(candidate.over_line) + float(candidate.under_line)) / 2.0, 0.01)
    st.session_state["market_label"] = f"{candidate.participant} {market_key}"
    st.session_state["over_book"] = candidate.over_book
    st.session_state["under_book"] = candidate.under_book
    st.session_state["over_line"] = float(candidate.over_line)
    st.session_state["under_line"] = float(candidate.under_line)
    st.session_state["over_american"] = int(candidate.over_american_odds)
    st.session_state["under_american"] = int(candidate.under_american_odds)
    st.session_state["odds_format"] = "American"
    st.session_state["stake_mode"] = "Balanced total stake"
    st.session_state["over_stake"] = float(candidate.over_stake)
    st.session_state["under_stake"] = float(candidate.under_stake)
    st.session_state["outcome_step"] = 1.0
    st.session_state["min_outcome"] = max(0.0, float(candidate.over_line) - 6.0)
    st.session_state["max_outcome"] = float(candidate.under_line) + 6.0
    st.session_state["distribution_model"] = "Poisson"
    st.session_state["distribution_mean"] = model_mean
    st.session_state["distribution_stdev"] = max(model_mean**0.5, 0.75)
    st.session_state["distribution_dispersion"] = float(st.session_state.get("candidate_dispersion", 0.15))


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 100%;
            padding-top: 1rem;
            padding-right: 1rem;
            padding-bottom: 2rem;
            padding-left: 1rem;
        }
        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            display: none;
            height: 0;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 1rem;
            background: #111827;
            box-shadow: none;
        }
        div[data-testid="stMetric"] * {
            color: #f8fafc !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
