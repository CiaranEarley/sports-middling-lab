import unittest

from sports_middling.middling import (
    BetLeg,
    BetSide,
    american_to_decimal,
    balanced_stakes,
    build_middle_analysis,
    decimal_to_implied_probability,
    normal_probabilities,
    poisson_probabilities,
    summarize_expected_value,
)


class MiddlingTests(unittest.TestCase):
    def test_converts_american_odds_to_decimal_and_probability(self):
        self.assertAlmostEqual(american_to_decimal(-110), 1.9090909091)
        self.assertAlmostEqual(american_to_decimal(120), 2.20)
        self.assertAlmostEqual(decimal_to_implied_probability(2.00), 0.50)

    def test_builds_middle_payoff_profile(self):
        analysis = build_middle_analysis(
            over_leg=BetLeg(
                side=BetSide.OVER,
                line=20.5,
                odds_decimal=american_to_decimal(-110),
                stake=100,
            ),
            under_leg=BetLeg(
                side=BetSide.UNDER,
                line=23.5,
                odds_decimal=american_to_decimal(-110),
                stake=100,
            ),
            min_outcome=19,
            max_outcome=25,
            step=1,
        )

        self.assertEqual(analysis.middle_outcomes, [21, 22, 23])
        self.assertAlmostEqual(analysis.lower_tail_profit, -9.0909090909)
        self.assertAlmostEqual(analysis.upper_tail_profit, -9.0909090909)
        self.assertAlmostEqual(analysis.middle_profit, 181.8181818182)
        self.assertAlmostEqual(analysis.max_loss, -9.0909090909)

    def test_balanced_stakes_equalize_tail_profit(self):
        over_stake, under_stake = balanced_stakes(
            total_stake=200,
            over_odds_decimal=american_to_decimal(120),
            under_odds_decimal=american_to_decimal(-110),
        )
        analysis = build_middle_analysis(
            over_leg=BetLeg(
                side=BetSide.OVER,
                line=5.5,
                odds_decimal=american_to_decimal(120),
                stake=over_stake,
            ),
            under_leg=BetLeg(
                side=BetSide.UNDER,
                line=7.5,
                odds_decimal=american_to_decimal(-110),
                stake=under_stake,
            ),
            min_outcome=0,
            max_outcome=12,
            step=1,
        )

        self.assertAlmostEqual(analysis.lower_tail_profit, analysis.upper_tail_profit)

    def test_summarizes_distribution_weighted_ev(self):
        analysis = build_middle_analysis(
            over_leg=BetLeg(
                side=BetSide.OVER,
                line=20.5,
                odds_decimal=american_to_decimal(-110),
                stake=100,
            ),
            under_leg=BetLeg(
                side=BetSide.UNDER,
                line=23.5,
                odds_decimal=american_to_decimal(-110),
                stake=100,
            ),
            min_outcome=18,
            max_outcome=28,
            step=1,
        )
        probabilities = normal_probabilities(
            analysis.outcomes,
            mean=22,
            stdev=3,
            step=1,
        )
        summary = summarize_expected_value(analysis, probabilities)

        self.assertGreater(summary.probability_middle, 0)
        self.assertGreater(summary.expected_profit, 0)
        self.assertLessEqual(summary.covered_probability, 1)

    def test_poisson_probability_grid(self):
        probabilities = poisson_probabilities([0, 1, 2, 3], mean=2)

        self.assertAlmostEqual(sum(probabilities.values()), 0.8571234605)
        self.assertGreater(probabilities[2], probabilities[0])


if __name__ == "__main__":
    unittest.main()
