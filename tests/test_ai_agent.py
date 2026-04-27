"""
tests/test_ai_agent.py
Unit tests for PawPalAgent (agentic workflow — Gemini AI task suggestions).

Gemini API calls are mocked via unittest.mock.patch (external service, not the logic layer).
All build_context and format_prompt logic is tested with real pawpal_system.py objects.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from pawpal_system import Owner, Pet, Task
from ai_agent import PawPalAgent, TaskSuggestion


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def pet() -> Pet:
    return Pet(name="Mochi", species="dog", breed="Shiba Inu", age=3)


@pytest.fixture
def owner() -> Owner:
    return Owner(name="Jordan", available_minutes=90)


@pytest.fixture
def owner_with_pet(owner: Owner, pet: Pet):
    owner.add_pet(pet)
    return owner, pet


@pytest.fixture
def agent(monkeypatch):
    """PawPalAgent with fake API key and mocked Gemini SDK."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    with patch("ai_agent.genai.Client"):
        return PawPalAgent()


SAMPLE_GEMINI_RESPONSE = json.dumps({
    "suggestions": [
        {
            "title": "Dental chew",
            "duration_minutes": 5,
            "priority": "medium",
            "category": "grooming",
            "preferred_time_slot": "evening",
            "reason": "Prevents tartar buildup in dogs",
            "reasoning": "Mochi has no grooming tasks and Shiba Inus are prone to dental issues.",
        },
        {
            "title": "Puzzle feeder",
            "duration_minutes": 15,
            "priority": "low",
            "category": "enrichment",
            "preferred_time_slot": "afternoon",
            "reason": "Mental stimulation reduces anxiety",
            "reasoning": "The afternoon slot is free and enrichment tasks are missing entirely.",
        },
    ]
})


# ===========================================================================
# TaskSuggestion
# ===========================================================================

class TestTaskSuggestion:

    def test_all_fields_stored_correctly(self, pet: Pet) -> None:
        suggestion = TaskSuggestion(
            pet_id=pet.id,
            title="Dental chew",
            duration_minutes=5,
            priority="medium",
            category="grooming",
            preferred_time_slot="evening",
            reason="Prevents tartar buildup",
            reasoning="Shiba Inus are prone to dental issues; no grooming tasks exist.",
        )
        assert suggestion.title == "Dental chew"
        assert suggestion.duration_minutes == 5
        assert suggestion.priority == "medium"
        assert suggestion.category == "grooming"
        assert suggestion.preferred_time_slot == "evening"
        assert suggestion.reason == "Prevents tartar buildup"
        assert "dental" in suggestion.reasoning.lower()
        assert suggestion.pet_id == pet.id


# ===========================================================================
# PawPalAgent.__init__
# ===========================================================================

class TestPawPalAgentInit:

    def test_missing_api_key_raises_value_error(self, monkeypatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with patch("ai_agent.genai.Client"):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                PawPalAgent()

    def test_valid_api_key_creates_instance(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        with patch("ai_agent.genai.Client"):
            ag = PawPalAgent()
        assert isinstance(ag, PawPalAgent)


# ===========================================================================
# build_context
# ===========================================================================

class TestBuildContext:

    def test_returns_pet_info(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        assert ctx["pet"]["name"] == "Mochi"
        assert ctx["pet"]["species"] == "dog"
        assert ctx["pet"]["breed"] == "Shiba Inu"
        assert ctx["pet"]["age"] == 3

    def test_returns_empty_task_lists_for_new_pet(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        assert ctx["pending_tasks"] == []
        assert ctx["completed_tasks"] == []
        assert ctx["overdue_tasks"] == []

    def test_pending_task_appears_in_pending_list(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Morning Walk", duration_minutes=20,
                          priority="high", category="walk", preferred_time_slot="morning")
        ctx = agent.build_context(owner, pet.id)
        assert any(t["title"] == "Morning Walk" for t in ctx["pending_tasks"])

    def test_completed_task_appears_in_completed_list(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Feeding", duration_minutes=10,
                          category="feeding", status="completed")
        ctx = agent.build_context(owner, pet.id)
        assert any(t["title"] == "Feeding" for t in ctx["completed_tasks"])
        assert not any(t["title"] == "Feeding" for t in ctx["pending_tasks"])

    def test_all_slots_empty_when_no_tasks(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        assert set(ctx["empty_slots"]) == {"morning", "afternoon", "evening"}

    def test_identifies_used_and_empty_slots(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Walk", duration_minutes=20,
                          preferred_time_slot="morning")
        ctx = agent.build_context(owner, pet.id)
        assert "morning" not in ctx["empty_slots"]
        assert "afternoon" in ctx["empty_slots"]
        assert "evening" in ctx["empty_slots"]

    def test_task_with_any_slot_does_not_fill_named_slots(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Walk", duration_minutes=20,
                          preferred_time_slot="any")
        ctx = agent.build_context(owner, pet.id)
        assert set(ctx["empty_slots"]) == {"morning", "afternoon", "evening"}

    def test_available_minutes_included(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        assert ctx["available_minutes"] == 90

    def test_invalid_pet_id_raises_value_error(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        with pytest.raises(ValueError):
            agent.build_context(owner, "nonexistent-pet-id")

    def test_overdue_task_with_past_due_date(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Old Vet Visit", duration_minutes=60,
                          category="meds", due_date="2020-01-01")
        ctx = agent.build_context(owner, pet.id)
        assert any(t["title"] == "Old Vet Visit" for t in ctx["overdue_tasks"])

    def test_future_due_date_not_overdue(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Future Checkup", duration_minutes=60,
                          category="meds", due_date="2099-12-31")
        ctx = agent.build_context(owner, pet.id)
        assert not any(t["title"] == "Future Checkup" for t in ctx["overdue_tasks"])

    def test_slot_usage_reflects_pending_tasks_only(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Done Walk", duration_minutes=20,
                          category="walk", preferred_time_slot="morning", status="completed")
        ctx = agent.build_context(owner, pet.id)
        assert "morning" in ctx["empty_slots"]


# ===========================================================================
# format_prompt
# ===========================================================================

class TestFormatPrompt:

    def test_returns_string(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        assert isinstance(agent.format_prompt(ctx), str)

    def test_includes_pet_name_and_species(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "Mochi" in prompt
        assert "dog" in prompt

    def test_includes_empty_slot_names(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Walk", duration_minutes=20,
                          preferred_time_slot="morning")
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "afternoon" in prompt
        assert "evening" in prompt

    def test_includes_json_format_instructions(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "suggestions" in prompt
        assert "JSON" in prompt

    def test_instructs_gemini_to_use_empty_slots(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "preferred_time_slot" in prompt

    def test_requests_reasoning_field(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "reasoning" in prompt


# ===========================================================================
# get_suggestions
# ===========================================================================

class TestGetSuggestions:

    def _agent_with_response(self, monkeypatch, response_text: str) -> PawPalAgent:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        with patch("ai_agent.genai.Client", return_value=mock_client):
            return PawPalAgent()

    def test_returns_list_of_task_suggestions(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert len(suggestions) == 2
        assert all(isinstance(s, TaskSuggestion) for s in suggestions)

    def test_suggestion_titles_match_response(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert suggestions[0].title == "Dental chew"
        assert suggestions[1].title == "Puzzle feeder"

    def test_suggestions_carry_correct_pet_id(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert all(s.pet_id == pet.id for s in suggestions)

    def test_suggestions_include_preferred_time_slot(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert suggestions[0].preferred_time_slot == "evening"
        assert suggestions[1].preferred_time_slot == "afternoon"

    def test_suggestions_include_reasoning(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert all(s.reasoning for s in suggestions)

    def test_strips_markdown_json_code_block(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        wrapped = f"```json\n{SAMPLE_GEMINI_RESPONSE}\n```"
        ag = self._agent_with_response(monkeypatch, wrapped)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert len(suggestions) == 2

    def test_strips_plain_code_block(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        wrapped = f"```\n{SAMPLE_GEMINI_RESPONSE}\n```"
        ag = self._agent_with_response(monkeypatch, wrapped)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert len(suggestions) == 2

    def test_empty_suggestions_returns_empty_list(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, json.dumps({"suggestions": []}))
        suggestions = ag.get_suggestions(owner, pet.id)
        assert suggestions == []

    def test_suggestion_duration_is_int(self, monkeypatch, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert all(isinstance(s.duration_minutes, int) for s in suggestions)

    def test_no_suggestion_conflicts_with_occupied_slots(self, monkeypatch, owner_with_pet) -> None:
        """Suggestions must target empty slots, not slots already used by pending tasks."""
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Walk", duration_minutes=20,
                          preferred_time_slot="morning")
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        occupied = {"morning"}
        for s in suggestions:
            if s.preferred_time_slot != "any":
                assert s.preferred_time_slot not in occupied, (
                    f"Suggestion '{s.title}' conflicts with occupied slot 'morning'"
                )


# ===========================================================================
# Guard 1 — Prompt scope lock
# ===========================================================================

class TestFormatPromptScopeGuard:

    def test_prompt_includes_scope_restriction(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "SCOPE" in prompt

    def test_prompt_restricts_to_pet_care_only(self, agent: PawPalAgent, owner_with_pet) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert "pet care" in prompt.lower()

    def test_prompt_instructs_empty_response_when_no_suggestions(
        self, agent: PawPalAgent, owner_with_pet
    ) -> None:
        owner, pet = owner_with_pet
        ctx = agent.build_context(owner, pet.id)
        prompt = agent.format_prompt(ctx)
        assert '{"suggestions": []}' in prompt


# ===========================================================================
# Guard 2 — Output validation (_is_valid_suggestion)
# ===========================================================================

VALID_SUGGESTION: dict = {
    "title": "Dental chew",
    "duration_minutes": 15,
    "priority": "medium",
    "category": "grooming",
    "preferred_time_slot": "evening",
    "reason": "Prevents tartar buildup",
    "reasoning": "Shiba Inus are prone to dental issues.",
}


class TestIsValidSuggestion:

    def test_valid_suggestion_returns_true(self) -> None:
        assert PawPalAgent._is_valid_suggestion(VALID_SUGGESTION) is True

    def test_invalid_priority_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "priority": "critical"}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_invalid_category_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "category": "finance"}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_invalid_slot_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "preferred_time_slot": "midnight"}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_duration_too_low_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "duration_minutes": 0}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_duration_too_high_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "duration_minutes": 1000}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_empty_title_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "title": ""}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_whitespace_only_title_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "title": "   "}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_title_too_long_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "title": "x" * 101}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_title_at_max_length_returns_true(self) -> None:
        s = {**VALID_SUGGESTION, "title": "x" * 100}
        assert PawPalAgent._is_valid_suggestion(s) is True

    def test_duration_at_min_boundary_returns_true(self) -> None:
        s = {**VALID_SUGGESTION, "duration_minutes": 5}
        assert PawPalAgent._is_valid_suggestion(s) is True

    def test_duration_at_max_boundary_returns_true(self) -> None:
        s = {**VALID_SUGGESTION, "duration_minutes": 480}
        assert PawPalAgent._is_valid_suggestion(s) is True

    def test_non_numeric_duration_returns_false(self) -> None:
        s = {**VALID_SUGGESTION, "duration_minutes": "lots"}
        assert PawPalAgent._is_valid_suggestion(s) is False

    def test_missing_slot_defaults_to_any_and_is_valid(self) -> None:
        s = {k: v for k, v in VALID_SUGGESTION.items() if k != "preferred_time_slot"}
        assert PawPalAgent._is_valid_suggestion(s) is True


# ===========================================================================
# Guard 2 — get_suggestions filters invalid API responses
# ===========================================================================

INVALID_CATEGORY_RESPONSE = json.dumps({
    "suggestions": [
        {
            "title": "Buy stocks",
            "duration_minutes": 15,
            "priority": "high",
            "category": "finance",
            "preferred_time_slot": "morning",
            "reason": "Off-topic",
            "reasoning": "Not pet care.",
        }
    ]
})

MIXED_VALID_INVALID_RESPONSE = json.dumps({
    "suggestions": [
        {
            "title": "Dental chew",
            "duration_minutes": 5,
            "priority": "medium",
            "category": "grooming",
            "preferred_time_slot": "evening",
            "reason": "Good for teeth",
            "reasoning": "Shiba Inus need dental care.",
        },
        {
            "title": "Bad suggestion",
            "duration_minutes": 9999,
            "priority": "critical",
            "category": "finance",
            "preferred_time_slot": "midnight",
            "reason": "Off-topic",
            "reasoning": "Not pet care.",
        },
    ]
})


class TestGetSuggestionsGuards:

    def _agent_with_response(self, monkeypatch, response_text: str) -> PawPalAgent:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        with patch("ai_agent.genai.Client", return_value=mock_client):
            return PawPalAgent()

    def test_invalid_category_suggestion_is_filtered(
        self, monkeypatch, owner_with_pet
    ) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, INVALID_CATEGORY_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert suggestions == []

    def test_only_valid_suggestions_returned_from_mixed_response(
        self, monkeypatch, owner_with_pet
    ) -> None:
        owner, pet = owner_with_pet
        ag = self._agent_with_response(monkeypatch, MIXED_VALID_INVALID_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        assert len(suggestions) == 1
        assert suggestions[0].title == "Dental chew"

    def test_existing_task_title_is_deduplicated(
        self, monkeypatch, owner_with_pet
    ) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="Dental chew", duration_minutes=5,
                          category="grooming")
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        titles = [s.title for s in suggestions]
        assert "Dental chew" not in titles

    def test_dedup_is_case_insensitive(
        self, monkeypatch, owner_with_pet
    ) -> None:
        owner, pet = owner_with_pet
        owner.create_task(pet_id=pet.id, title="dental chew", duration_minutes=5,
                          category="grooming")
        ag = self._agent_with_response(monkeypatch, SAMPLE_GEMINI_RESPONSE)
        suggestions = ag.get_suggestions(owner, pet.id)
        titles = [s.title for s in suggestions]
        assert "Dental chew" not in titles
