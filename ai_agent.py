"""
ai_agent.py
Agentic workflow for PawPal+ — Gemini-powered smart task suggestions.

PawPalAgent analyzes a pet's current care data (existing tasks, species/breed/age,
schedule gaps, overdue items) and returns AI-generated TaskSuggestion objects.
Suggestions are assigned to empty time slots to avoid soft scheduling conflicts.
"""

import json
import os
from dataclasses import dataclass
from datetime import date as date_type

from dotenv import load_dotenv
from google import genai

from pawpal_system import Owner

load_dotenv()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TaskSuggestion:
    """An AI-generated care task suggestion for a specific pet.

    preferred_time_slot is set to an empty slot so the suggestion does not
    conflict with tasks already occupying morning/afternoon/evening.
    reasoning explains the agent's analysis that led to this suggestion.
    reason is a one-sentence human-facing summary.
    """

    pet_id: str
    title: str
    duration_minutes: int
    priority: str
    category: str
    preferred_time_slot: str
    reason: str
    reasoning: str


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class PawPalAgent:
    """Gemini-powered agent that analyzes pet care data and suggests missing tasks.

    Uses gemini-2.5-flash via the Google Generative AI SDK.
    Requires GEMINI_API_KEY environment variable.
    """

    MODEL_NAME: str = "gemini-2.5-flash"

    def __init__(self) -> None:
        """Initialize agent. Raises ValueError if GEMINI_API_KEY is not set."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        self._client = genai.Client(api_key=api_key)

    def build_context(self, owner: Owner, pet_id: str) -> dict:
        """Build structured care context for a pet to feed into the prompt.

        Raises:
            ValueError: if pet_id is not found in owner's pets.
        """
        pet = owner.get_pet(pet_id)
        if not pet:
            raise ValueError(f"Pet '{pet_id}' not found")

        tasks = owner.get_tasks(pet_id)
        today = str(date_type.today())

        pending = [t for t in tasks if t.status == "pending"]
        completed = [t for t in tasks if t.status == "completed"]
        overdue = [
            t for t in tasks
            if t.status == "pending" and t.due_date and t.due_date < today
        ]

        slot_usage: dict[str, list[str]] = {"morning": [], "afternoon": [], "evening": []}
        for task in pending:
            if task.preferred_time_slot in slot_usage:
                slot_usage[task.preferred_time_slot].append(task.title)

        empty_slots = [slot for slot, task_list in slot_usage.items() if not task_list]

        return {
            "pet": {
                "name": pet.name,
                "species": pet.species,
                "breed": pet.breed,
                "age": pet.age,
            },
            "pending_tasks": [
                {
                    "title": t.title,
                    "category": t.category,
                    "duration_minutes": t.duration_minutes,
                    "recurrence": t.recurrence,
                    "preferred_time_slot": t.preferred_time_slot,
                }
                for t in pending
            ],
            "completed_tasks": [
                {"title": t.title, "category": t.category}
                for t in completed
            ],
            "overdue_tasks": [
                {"title": t.title, "category": t.category}
                for t in overdue
            ],
            "empty_slots": empty_slots,
            "available_minutes": owner.available_minutes,
        }

    def format_prompt(self, context: dict) -> str:
        """Format care context into a Gemini prompt requesting conflict-free task suggestions."""
        pet = context["pet"]
        pending = context["pending_tasks"]
        completed = context["completed_tasks"]
        overdue = context["overdue_tasks"]
        empty_slots = context["empty_slots"]
        available = context["available_minutes"]

        existing_titles = [t["title"] for t in pending + completed]
        slots_str = ", ".join(empty_slots) if empty_slots else "none available"

        return f"""You are a certified pet care expert. Analyze this pet's current care routine and suggest 2-4 missing or beneficial tasks.

Pet profile: {pet["name"]} — {pet["age"]}-year-old {pet["breed"]} {pet["species"]}
Daily time budget: {available} minutes

Current pending tasks:
{json.dumps(pending, indent=2) if pending else "None"}

Completed tasks:
{json.dumps(completed, indent=2) if completed else "None"}

Overdue tasks (past due date):
{json.dumps(overdue, indent=2) if overdue else "None"}

Available (empty) time slots: {slots_str}

RULES:
1. Do NOT suggest tasks already in the list: {existing_titles}
2. Assign each suggestion to one of the available empty time slots above. If no slots are available, use "any".
3. Consider the species, breed, and age to make species-appropriate suggestions.
4. Provide a detailed "reasoning" explaining exactly WHY you are suggesting this task for this specific pet — reference the pet's breed, age, existing gaps, or overdue items.
5. Provide a short one-sentence "reason" summary for display.

Respond ONLY with valid JSON in this exact format — no extra text:
{{
  "suggestions": [
    {{
      "title": "task name",
      "duration_minutes": 15,
      "priority": "high|medium|low",
      "category": "walk|feeding|meds|grooming|enrichment|other",
      "preferred_time_slot": "morning|afternoon|evening|any",
      "reason": "one sentence why this matters for this pet",
      "reasoning": "detailed explanation referencing breed, age, existing tasks, gaps, or overdue items"
    }}
  ]
}}"""

    def get_suggestions(self, owner: Owner, pet_id: str) -> list[TaskSuggestion]:
        """Analyze pet care data via Gemini and return AI-generated task suggestions.

        Each suggestion targets an empty time slot to avoid scheduling conflicts.
        """
        context = self.build_context(owner, pet_id)
        prompt = self.format_prompt(context)

        response = self._client.models.generate_content(
            model=self.MODEL_NAME,
            contents=prompt,
        )
        text = response.text.strip()

        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]

        data = json.loads(text.strip())

        return [
            TaskSuggestion(
                pet_id=pet_id,
                title=s["title"],
                duration_minutes=int(s["duration_minutes"]),
                priority=s["priority"],
                category=s["category"],
                preferred_time_slot=s.get("preferred_time_slot", "any"),
                reason=s["reason"],
                reasoning=s.get("reasoning", ""),
            )
            for s in data.get("suggestions", [])
        ]
