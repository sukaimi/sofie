"""Sofie — Account Manager agent.

Primary chat interface. Receives brief, manages conversation, presents
output, handles feedback, delivers final files. Uses Sonnet for
fast, warm, conversational responses.
"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.models import Job


class SofieAgent(BaseAgent):
    """Account manager — the user-facing personality of SOFIE.

    Sofie translates between the technical pipeline and the human
    client. She explains what's happening, reports issues clearly,
    handles feedback intelligently, and delivers with warmth.
    """

    name = "sofie"
    model = "sonnet"
    system_prompt = (
        "You are Sofie, a creative account manager at a social media agency.\n"
        "SOFIE stands for Studio Orchestrator For Intelligent Execution.\n"
        "You are the human face of the SOFIE platform, built by Code&Canvas.\n\n"
        "Your personality:\n"
        "- Warm and professional. You feel like a real person, not a chatbot.\n"
        "- Proactive. You anticipate what clients need before they ask.\n"
        "- Clear. You explain things in plain language, no jargon.\n"
        "- Honest. You never promise what you cannot deliver.\n"
        "- Patient. You handle confusion and frustration with grace.\n\n"
        "Your capabilities:\n"
        "- Receive a creative brief (.docx upload)\n"
        "- Provide the brief template download link: /api/brief-template\n"
        "- Oversee an internal team that validates, composes, and checks the work\n"
        "- Present the finished visual and manage revision requests\n"
        "- Deliver the final files as a download link\n\n"
        "Your limitations (be honest about these):\n"
        "- You cannot generate videos\n"
        "- You cannot do batch processing (one job at a time)\n"
        "- You cannot guarantee first-pass perfection — revisions are normal\n"
        "- You have a maximum of 2 revision rounds per job\n\n"
        "Never:\n"
        "- Use emojis unless the client uses them first\n"
        "- Apologise excessively\n"
        "- Make up information about the brand\n"
        "- Proceed past a BLOCKER without resolution\n"
        "- Start a 3rd revision round — escalate to the team instead\n\n"
        "Language: English only."
    )

    async def execute(
        self, job: Job, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate a contextual response for the current conversation state.

        Input contains the conversation history and any pipeline state
        that needs to be communicated to the user (blockers, output, etc).
        """
        action = input_data.get("action", "chat")
        conversation_history = input_data.get("messages", [])

        if action == "greet":
            return {"message": self._greeting()}
        elif action == "confirm_brief":
            return await self._confirm_brief(job, input_data, conversation_history)
        elif action == "report_blockers":
            return await self._report_blockers(job, input_data, conversation_history)
        elif action == "report_asset_issues":
            return await self._report_issues(job, input_data, conversation_history, "asset")
        elif action == "report_font_issues":
            return self._report_font_issues(input_data)
        elif action == "present_output":
            return await self._present_output(job, input_data, conversation_history)
        elif action == "evaluate_feedback":
            return await self._evaluate_feedback(job, input_data, conversation_history)
        elif action == "deliver":
            return await self._deliver(job, input_data, conversation_history)
        elif action == "escalate":
            return self._escalate(input_data)
        else:
            return await self._chat(job, input_data, conversation_history)

    def _greeting(self) -> str:
        """Sofie's opening line — warm but purposeful."""
        return (
            "Hi! I'm Sofie, your creative account manager. "
            "I help brands create social media visuals — static banners "
            "for Instagram, Facebook, and LinkedIn.\n\n"
            "To get started, upload a completed brief using the upload area below. "
            "If you don't have one yet, [download our brief template here](/api/brief-template).\n\n"
            "What can I help you create today?"
        )

    async def _confirm_brief(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
    ) -> dict[str, Any]:
        """Present extracted brief fields for user confirmation.

        Shows the user what was extracted so they can catch errors
        before the pipeline spends tokens on validation and composition.
        """
        brief = input_data.get("brief_fields", job.brief_json)
        warnings = input_data.get("warnings", [])

        parts = ["Here's what I found in your brief:\n"]
        parts.append(f"**Brand:** {brief.get('brand_name', 'Not specified')}")
        parts.append(f"**Platform:** {brief.get('platform', 'Not specified')}")

        sizes = brief.get("output_sizes", [])
        if isinstance(sizes, list):
            parts.append(f"**Sizes:** {', '.join(sizes)}")
        else:
            parts.append(f"**Sizes:** {sizes}")

        parts.append(f"**Key message:** {brief.get('key_message', 'Not specified')}")
        parts.append(f"**Headline:** {brief.get('headline_text', 'Not specified')}")

        if brief.get("cta_text"):
            parts.append(f"**CTA:** {brief['cta_text']}")
        if brief.get("hero_image_links"):
            parts.append(f"**Hero image:** Provided")
        if brief.get("logo_link"):
            parts.append(f"**Logo:** Provided")
        if brief.get("brand_font_link"):
            parts.append(f"**Font:** Provided")

        if warnings:
            parts.append("\n**Heads up:**")
            for w in warnings:
                parts.append(f"- {w}")

        parts.append("\nIs this all correct?")

        return {"message": "\n".join(parts)}

    async def _report_blockers(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
    ) -> dict[str, Any]:
        """Report missing required fields clearly with fix instructions."""
        blockers = input_data.get("blockers", [])

        parts = ["I've reviewed your brief and found issues before we can proceed:\n"]
        for b in blockers:
            parts.append(f"**REQUIRED — {b['field']}:** {b['message']}")

        parts.append(
            "\nOnce you've updated your brief, please re-upload it "
            "and I'll continue from there."
        )

        return {"message": "\n".join(parts)}

    async def _report_issues(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
        issue_type: str,
    ) -> dict[str, Any]:
        """Report asset or validation issues with platform-specific advice."""
        blockers = input_data.get("blockers", [])

        parts = [f"I found some {issue_type} issues:\n"]
        for b in blockers:
            parts.append(f"- **{b['field']}:** {b['message']}")

        parts.append("\nPlease fix these and I'll continue.")

        return {"message": "\n".join(parts)}

    def _report_font_issues(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Report unsupported characters in the brand font."""
        chars = input_data.get("font_issues", [])
        chars_str = ", ".join(f"'{c}'" for c in chars)

        return {
            "message": (
                f"Quick heads up before I start compositing:\n\n"
                f"Your brand font doesn't support these characters: {chars_str}\n\n"
                "I can either:\n"
                "1. Use a fallback system font for those characters only\n"
                "2. You can rephrase to avoid them\n\n"
                "Which would you prefer?"
            )
        }

    async def _present_output(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
    ) -> dict[str, Any]:
        """Present the composited output with rationale and feedback menu."""
        rationale = input_data.get("rationale", "")
        size = input_data.get("size", "")
        platform = job.brief_json.get("platform", "")

        messages = history + [
            {
                "role": "user",
                "content": (
                    f"The visual is ready for {size} ({platform}). "
                    f"Rationale: {rationale}. "
                    "Write a brief, warm presentation message and include "
                    "the guided feedback menu."
                ),
            }
        ]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="present_output",
            max_tokens=512,
        )

        return {"message": response}

    async def _evaluate_feedback(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
    ) -> dict[str, Any]:
        """Classify user feedback as actionable/vague/unactionable/contradictory."""
        feedback = input_data.get("feedback", "")

        messages = history + [
            {
                "role": "user",
                "content": (
                    f"Evaluate this client feedback: \"{feedback}\"\n\n"
                    "Classify as: ACTIONABLE, VAGUE, UNACTIONABLE, or CONTRADICTORY.\n"
                    "If VAGUE, suggest what you think they mean.\n"
                    "If CONTRADICTORY, explain the conflict.\n\n"
                    "Respond as JSON: {\"type\": \"...\", \"message\": \"...\", "
                    "\"revision_instructions\": \"...\"}"
                ),
            }
        ]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="evaluate_feedback",
            max_tokens=512,
        )

        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {"type": "ACTIONABLE", "message": response, "revision_instructions": feedback}

    async def _deliver(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
    ) -> dict[str, Any]:
        """Deliver final files with download link — warm closing."""
        download_url = input_data.get("download_url", "")

        return {
            "message": (
                f"All approved! Here are your files:\n\n"
                f"[Download your visuals]({download_url})\n\n"
                "Great working with you. If you need anything else, "
                "just start a new chat."
            )
        }

    def _escalate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Calm escalation message — reassure the user."""
        reason = input_data.get("reason", "")

        if "revision_limit" in reason:
            msg = (
                "I've done my best across two rounds of revisions. "
                "To make sure you get exactly what you need, "
                "I'm passing this to the team for a closer look. "
                "They'll review and come back to you with options."
            )
        elif "qa_failed" in reason:
            msg = (
                "I've made several attempts to get this right but "
                "my quality check keeps flagging issues. "
                "I'm sending this to the team for a closer look. "
                "They'll review and come back to you shortly."
            )
        elif "cost_ceiling" in reason:
            msg = (
                "I've paused work on your job for a moment — "
                "this one is taking a bit more processing than usual. "
                "The team is reviewing and will continue shortly."
            )
        else:
            msg = (
                "I'm flagging this to the team for some extra help. "
                "Someone will be in touch shortly."
            )

        return {"message": msg}

    async def _chat(
        self,
        job: Job,
        input_data: dict[str, Any],
        history: list[dict],
    ) -> dict[str, Any]:
        """Free-form conversational response for general messages."""
        user_message = input_data.get("user_message", "")
        messages = history + [{"role": "user", "content": user_message}]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="chat",
            max_tokens=512,
        )

        return {"message": response}
