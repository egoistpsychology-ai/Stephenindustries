"""Offline tests for Phase 1 guardrails and task orchestration."""
import unittest
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import patch

from backend.config import settings
from backend.agents import team
from backend.guardrails.cost import CostLimitExceeded, CostTracker, llm_cost_event_scope
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
        config = replace(settings, groq_input_usd_per_million=1.0, groq_output_usd_per_million=2.0)
        tracker = CostTracker("task-1", 1.0, settings=config, on_cost=events.append)
        tracker.add_usage("groq", 1000, 500)
        self.assertAlmostEqual(tracker.usd, 0.002)
        self.assertEqual(events[-1]["type"], "cost")
        self.assertEqual(events[-1]["task_id"], "task-1")

    def test_estimates_when_provider_usage_is_missing_and_warns(self):
        events, warnings = [], []
        tracker = CostTracker("task-estimate", 1.0, settings=settings,
                              on_cost=events.append, on_warning=warnings.append)
        class Event:
            messages = [{"role": "user", "content": "a" * 400}]
            response = "b" * 400
        tracker.add_event_usage("groq", Event())
        self.assertGreater(tracker.tokens_in, 0)
        self.assertGreater(tracker.tokens_out, 0)
        self.assertGreater(tracker.usd, 0)
        self.assertTrue(warnings)
        self.assertEqual(events[-1]["type"], "cost")

    def test_real_crewai_event_bus_accounts_fake_completion_and_breaks_budget(self):
        from crewai.utilities.events import (
            LLMCallCompletedEvent,
            LLMCallType,
            crewai_event_bus,
        )

        config = replace(
            settings,
            groq_input_usd_per_million=1000.0,
            groq_output_usd_per_million=1000.0,
        )
        tracker = CostTracker("event-bus-task", 0.001, settings=config)
        response = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=2, completion_tokens=0)
        )
        event = LLMCallCompletedEvent(
            response=response,
            call_type=LLMCallType.LLM_CALL,
        )
        with llm_cost_event_scope(tracker, "groq"):
            # Emit through CrewAI's actual v0.130.0 event bus, not a direct tracker call.
            crewai_event_bus.emit(object(), event)
            self.assertGreater(tracker.usd, 0)
            with self.assertRaises(CostLimitExceeded):
                tracker.check_limit()

    def test_raises_when_cost_exceeds_limit(self):
        config = replace(settings, groq_input_usd_per_million=1000.0, groq_output_usd_per_million=1000.0)
        tracker = CostTracker("task-2", 0.001, settings=config)
        with self.assertRaisesRegex(CostLimitExceeded, "task stopped"):
            tracker.add_usage("groq", 2, 0)


class RunTeamTaskTests(unittest.TestCase):
    def setUp(self):
        self.agents = (object(), object(), object())

    def test_cost_breaker_stops_task_and_emits_done(self):
        config = replace(settings, groq_api_key="test", deepseek_api_key="test",
                         max_cost_usd_per_task=0.01,
                         groq_input_usd_per_million=1.0,
                         groq_output_usd_per_million=1.0)
        events, calls = [], []
        def fake_run_one(agent, description, expected_output, *, provider, tracker, on_event):
            calls.append(provider)
            tracker.add_usage("groq", 100_000, 0)
            return '{"seer_task":"backend","escanor_task":"frontend"}'
        with patch.object(team, "build_agents", return_value=self.agents), \
             patch.object(team, "_run_one", side_effect=fake_run_one):
            with self.assertRaises(CostLimitExceeded):
                team.run_team_task("test request", task_id="cost-breaker", on_event=events.append, config=config)
        self.assertEqual(len(calls), 1)
        self.assertEqual(events[-1]["type"], "done")
        self.assertTrue(any(event["type"] == "error" for event in events))

    def test_zero_delegation_limit_raises_and_emits_done(self):
        config = replace(settings, groq_api_key="test", deepseek_api_key="test",
                         max_delegations_per_task=0)
        events, calls = [], []
        def fake_run_one(agent, description, expected_output, *, provider, tracker, on_event):
            calls.append(provider)
            tracker.add_usage(provider, 1, 1)
            return '{"seer_task":"backend","escanor_task":"frontend"}'
        with patch.object(team, "build_agents", return_value=self.agents), \
             patch.object(team, "_run_one", side_effect=fake_run_one):
            with self.assertRaises(DelegationLimitExceeded):
                team.run_team_task("test request", task_id="delegation-limit", on_event=events.append, config=config)
        self.assertEqual(len(calls), 1)
        self.assertEqual(events[-1]["type"], "done")
        self.assertTrue(any(event["type"] == "error" for event in events))


if __name__ == "__main__":
    unittest.main()
