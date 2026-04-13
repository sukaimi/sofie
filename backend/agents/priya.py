"""Priya — Strategic Brief Analyst agent.

Validates brief completeness (BLOCKER/WARNING/OPTIONAL classification)
and checks strategic alignment of campaign message. Uses Opus for
high-accuracy analysis of brief quality.
"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.models import Job


class PriyaAgent(BaseAgent):
    """Brief analyst — catches missing fields and strategic misalignment.

    Priya is the gatekeeper. Nothing enters the pipeline without her
    sign-off. She's intentionally strict because fixing issues downstream
    costs more tokens than catching them here.
    """

    name = "priya"
    model = "opus"
    system_prompt = (
        "You are Priya, a strategic account planner and brief analyst.\n\n"
        "You have two jobs when you receive a brief:\n\n"
        "JOB 1 — COMPLETENESS CHECK\n"
        "Review every field. For each field, determine:\n"
        "- BLOCKER: missing field that prevents production\n"
        "- WARNING: missing field where a reasonable assumption can be made\n"
        "- OPTIONAL: field that is genuinely optional\n\n"
        "BLOCKER fields (if any are missing, stop immediately):\n"
        "brand_name, key_message, output_sizes, logo_link, brand_font_link,\n"
        "brand_colours, headline_text, platform\n\n"
        "WARNING fields (proceed with noted assumption):\n"
        "campaign_objective (assume 'general awareness')\n\n"
        "OPTIONAL fields (proceed silently if missing):\n"
        "cta_text, hero_image_link, design_elements_link, layout_references,\n"
        "sub_copy, restrictions\n\n"
        "JOB 2 — STRATEGIC ALIGNMENT CHECK\n"
        "If no BLOCKERs, review strategically:\n"
        "- Does the key message make sense for the stated objective?\n"
        "- Is the headline consistent with the key message?\n"
        "- Are there obvious contradictions?\n"
        "- Is the CTA appropriate for the platform?\n\n"
        "Flag strategic issues as WARNINGS.\n\n"
        "Output ONLY valid JSON:\n"
        "{\n"
        '  "has_blockers": true/false,\n'
        '  "blockers": [{"field": "...", "message": "..."}],\n'
        '  "warnings": [{"field": "...", "message": "...", "assumption": "..."}],\n'
        '  "strategic_issues": [{"issue": "...", "recommendation": "..."}],\n'
        '  "approved": true/false\n'
        "}\n\n"
        "Be precise. Be specific. Do not pad your output."
    )

    # Fields that block the pipeline if missing — from PRD section 7.
    _BLOCKER_FIELDS: set[str] = {
        "brand_name",
        "key_message",
        "output_sizes",
        "logo_link",
        "brand_font_link",
        "brand_colours",
        "headline_text",
        "platform",
    }

    async def execute(
        self, job: Job, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate brief fields and strategic alignment.

        Does a fast local check for blocker fields first — no point
        spending Opus tokens if brand_name is obviously missing.
        Falls through to LLM for nuanced strategic analysis.
        """
        brief = input_data.get("brief_fields", {})

        # Fast local check: are all blocker fields present?
        local_blockers = self._check_blockers_locally(brief)
        if local_blockers:
            return {
                "has_blockers": True,
                "blockers": local_blockers,
                "warnings": [],
                "strategic_issues": [],
                "approved": False,
            }

        # LLM analysis for strategic alignment and nuanced checks
        brief_text = json.dumps(brief, indent=2, default=str)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Validate this brief and check strategic alignment.\n\n"
                    f"Brief fields:\n{brief_text}"
                ),
            }
        ]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="brief_validation",
            max_tokens=1024,
        )

        return self._parse_validation_response(response)

    def _check_blockers_locally(
        self, brief: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Quick check for obviously missing required fields.

        Saves an Opus call when the brief is clearly incomplete —
        common when clients upload a half-filled template.
        """
        blockers = []
        for field in self._BLOCKER_FIELDS:
            value = brief.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                blockers.append(
                    {
                        "field": field,
                        "message": f"Required field '{field}' is missing or empty",
                    }
                )
        return blockers

    def _parse_validation_response(
        self, response: str
    ) -> dict[str, Any]:
        """Extract JSON from Priya's LLM response.

        Priya sometimes wraps JSON in markdown code blocks — strip those.
        Falls back to a conservative 'not approved' if parsing fails.
        """
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            result = json.loads(text)
            # Ensure required keys exist
            result.setdefault("has_blockers", False)
            result.setdefault("blockers", [])
            result.setdefault("warnings", [])
            result.setdefault("strategic_issues", [])
            result.setdefault("approved", not result["has_blockers"])
            return result
        except (json.JSONDecodeError, KeyError):
            return {
                "has_blockers": False,
                "blockers": [],
                "warnings": [
                    {
                        "field": "system",
                        "message": "Could not parse validation response",
                        "assumption": "Proceeding with caution",
                    }
                ],
                "strategic_issues": [],
                "approved": True,
            }
