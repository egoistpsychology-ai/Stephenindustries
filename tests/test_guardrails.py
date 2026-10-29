"""Unit tests for Phase 1 guardrails; no provider API calls required."""
import unittest
from dataclasses import replace

from backend.config import settings
from backend.guardrails.cost import CostLimitExceeded, CostTracker
from backend.guardrails.delegation import DelegationCounter, DelegationLimitExceeded


class DelegationCounterTests(unittest.TestCase):
    def test_allows_exactly_the_configured_number(self):
        counter = DelegationCounter(maximum=2)
        counter.consume("seer")
        counter.consume("escanor")
        self.assertEqual(counter.count, 2)

    def test_rejects_next_delegation(self):
        counter = DelegationCounter(maximum=1)
        counter.consume("seer")
        with self.assertRaises(DelegationLimitExceeded):
            counter.consume("escanor")
        self.assertEqual(counter.count, 1)


class CostTrackerTests(unittest.TestCase):
    def test_calculates_usage_and_emits_cost_event(self):
        events = []
        config = replace(
            settings,
            groq_input_usd_per_million=1.0,
            groq_output_usd_per_million=2.0,
        )
        tracker = CostTracker("task-1", 1.0, settings=config, on_cost=events.append)
        tracker.add_usage("groq", 1000, 500)
        self.assertAlmostEqual(tracker.usd, 0.002)
        self.assertEqual(tracker.tokens_in, 1000)
        self.assertEqual(tracker.tokens_out, 500)
        self.assertEqual(events[-1]["type"], "cost")
        self.assertEqual(events[-1]["task_id"], "task-1")

    def test_raises_when_cost_exceeds_limit(self):
        config = replace(
            settings,
            groq_input_usd_per_million=1000.0,
            groq_output_usd_per_million=1000.0,
        )
        tracker = CostTracker("task-2", 0.001, settings=config)
        with self.assertRaisesRegex(CostLimitExceeded, "task stopped"):
            tracker.add_usage("groq", 2, 0)

    def test_does_not_raise_at_exact_limit(self):
        config = replace(
            settings,
            groq_input_usd_per_million=1.0,
            groq_output_usd_per_million=1.0,
        )
        tracker = CostTracker("task-3", 0.001, settings=config)
        tracker.add_usage("groq", 1000, 0)
        self.assertAlmostEqual(tracker.usd, 0.001)


if __name__ == "__main__":
    unittest.main()
