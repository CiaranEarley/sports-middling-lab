import unittest

from sports_middling.sports_odds_api import (
    build_arbitrage_candidates,
    build_middle_candidates,
    build_outright_dutch_candidates,
    extract_market_keys,
    extract_market_outcome_quotes,
    extract_prop_quotes,
)


class SportsOddsApiTests(unittest.TestCase):
    def test_extracts_player_prop_quotes_and_candidates(self):
        payload = {
            "id": "event-1",
            "commence_time": "2026-05-25T20:00:00Z",
            "home_team": "Home Team",
            "away_team": "Away Team",
            "bookmakers": [
                {
                    "title": "Book A",
                    "markets": [
                        {
                            "key": "player_points",
                            "outcomes": [
                                {
                                    "name": "Over",
                                    "description": "Example Player",
                                    "price": -110,
                                    "point": 20.5,
                                },
                                {
                                    "name": "Under",
                                    "description": "Example Player",
                                    "price": -110,
                                    "point": 20.5,
                                },
                            ],
                        }
                    ],
                },
                {
                    "title": "Book B",
                    "markets": [
                        {
                            "key": "player_points",
                            "outcomes": [
                                {
                                    "name": "Over",
                                    "description": "Example Player",
                                    "price": -105,
                                    "point": 22.5,
                                },
                                {
                                    "name": "Under",
                                    "description": "Example Player",
                                    "price": -115,
                                    "point": 23.5,
                                },
                            ],
                        }
                    ],
                },
            ]
        }

        quotes = extract_prop_quotes(payload, "player_points")
        candidates = build_middle_candidates(quotes, total_stake=200)

        self.assertEqual(len(quotes), 4)
        self.assertEqual(candidates[0].participant, "Example Player")
        self.assertEqual(candidates[0].event_id, "event-1")
        self.assertEqual(candidates[0].event_label, "Away Team at Home Team")
        self.assertEqual(candidates[0].over_book, "Book A")
        self.assertEqual(candidates[0].under_book, "Book B")
        self.assertEqual(candidates[0].over_line, 20.5)
        self.assertEqual(candidates[0].under_line, 23.5)
        self.assertGreater(candidates[0].middle_width, 0)

    def test_extracts_available_market_keys(self):
        payload = {
            "bookmakers": [
                {
                    "markets": [
                        {"key": "player_points"},
                        {"key": "player_rebounds"},
                    ]
                },
                {
                    "markets": [
                        {"key": "player_points"},
                        {"key": "totals"},
                    ]
                },
            ]
        }

        self.assertEqual(
            extract_market_keys(payload),
            ["player_points", "player_rebounds", "totals"],
        )

    def test_builds_h2h_arbitrage_candidate(self):
        payload = {
            "id": "event-2",
            "commence_time": "2026-05-25T22:00:00Z",
            "home_team": "Home Team",
            "away_team": "Away Team",
            "bookmakers": [
                {
                    "title": "Book A",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Home Team", "price": 120},
                                {"name": "Away Team", "price": -140},
                            ],
                        }
                    ],
                },
                {
                    "title": "Book B",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Home Team", "price": -140},
                                {"name": "Away Team", "price": 120},
                            ],
                        }
                    ],
                },
            ],
        }

        quotes = extract_market_outcome_quotes(payload, ["h2h"])
        candidates = build_arbitrage_candidates(quotes, total_stake=100)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].signal, "TAKE")
        self.assertAlmostEqual(candidates[0].implied_probability, 2 / 2.2)
        self.assertAlmostEqual(candidates[0].guaranteed_profit, 10)
        self.assertEqual(len(candidates[0].legs), 2)

    def test_builds_outright_dutching_candidate(self):
        payload = {
            "id": "event-3",
            "commence_time": "2026-05-25T22:00:00Z",
            "sport_title": "Golf",
            "bookmakers": [
                {
                    "title": "Book A",
                    "markets": [
                        {
                            "key": "outrights",
                            "outcomes": [
                                {"name": "Golfer A", "price": 2000},
                                {"name": "Golfer B", "price": 1800},
                            ],
                        }
                    ],
                },
                {
                    "title": "Book B",
                    "markets": [
                        {
                            "key": "outrights",
                            "outcomes": [
                                {"name": "Golfer A", "price": 2200},
                                {"name": "Golfer C", "price": 2500},
                            ],
                        }
                    ],
                },
            ],
        }

        quotes = extract_market_outcome_quotes(payload, ["outrights"])
        candidates = build_outright_dutch_candidates(
            quotes,
            total_stake=100,
            max_runners=3,
            max_implied_probability=0.2,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].runner_count, 3)
        self.assertGreater(candidates[0].profit_if_hit, 0)
        self.assertEqual(candidates[0].legs[0].payout, candidates[0].legs[1].payout)


if __name__ == "__main__":
    unittest.main()
