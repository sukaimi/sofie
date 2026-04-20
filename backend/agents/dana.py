"""Dana — QA Inspector agent.

Runs 3-check vision inspection on composited output: layout quality,
brief compliance, and technical specification. Pass/fail with scores
and specific issues for Celeste to fix.
"""

import json
from typing import Any

from backend.agents.base import BaseAgent
from backend.models import Job


class DanaAgent(BaseAgent):
    """QA inspector — 3-check vision audit of every composited image.

    Dana is the last gate before the user sees output. She checks
    layout, brief compliance, and technical specs. No creative opinions —
    only facts vs specification.
    """

    name = "dana"
    model = "sonnet"
    system_prompt = (
        "You are Dana, a QA inspector at a creative studio.\n\n"
        "You receive a composited image and the original brief + plan.\n"
        "Run 3 checks and report pass/fail with specific issues.\n\n"
        "IMPORTANT CONTEXT: This is a POC system using programmatic compositing\n"
        "(Pillow + Cairo), not professional design software. Be pragmatic —\n"
        "pass the image if it is good enough to show the client for feedback.\n"
        "The client will request revisions anyway. Don't block on minor issues.\n"
        "Only fail if something is genuinely broken or misleading.\n\n"
        "CHECK 1 — LAYOUT QUALITY (pass threshold: 50)\n"
        "- Are elements visible and not clipped off-canvas?\n"
        "- Is there a reasonable visual hierarchy?\n"
        "- Is spacing acceptable (not perfect, just not broken)?\n\n"
        "CHECK 2 — BRIEF COMPLIANCE (pass threshold: 50)\n"
        "- Is the headline present?\n"
        "- Is the CTA present if specified?\n"
        "- Does the general mood feel right?\n"
        "- Are there any restricted elements present?\n\n"
        "CHECK 3 — TECHNICAL SPECIFICATION (pass threshold: 60)\n"
        "- Are dimensions roughly correct?\n"
        "- Is text readable (not perfect, just readable)?\n"
        "- Is the logo present?\n\n"
        "OVERALL PASS: pass if at least 2 of 3 checks pass.\n"
        "When in doubt, PASS and let the client give feedback.\n\n"
        "Output ONLY valid JSON:\n"
        "{\n"
        '  "check1_layout": {"pass": true/false, "score": 0-100, "issues": []},\n'
        '  "check2_brief": {"pass": true/false, "score": 0-100, "issues": []},\n'
        '  "check3_spec": {"pass": true/false, "score": 0-100, "issues": []},\n'
        '  "overall_pass": true/false,\n'
        '  "recommendation": "send_to_user|revise_composition|revise_layout|escalate",\n'
        '  "revision_notes": "Specific instructions for revision if needed"\n'
        "}\n\n"
        "Be specific about issues but be lenient. Log issues as notes,\n"
        "not as reasons to fail. Only fail on genuinely broken output."
    )

    async def execute(
        self, job: Job, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Run 3-check QA on the composited image.

        Sends the image via vision alongside the brief and plan context
        so Dana can compare what was requested vs what was produced.
        """
        image_path = input_data.get("image_path")
        brief = input_data.get("brief_fields", {})
        plan = input_data.get("composition_plan", {})
        target_dimensions = input_data.get("dimensions", "1080x1080")

        if not image_path:
            return self._fail_result("No image provided for QA")

        # Read the composited image for vision analysis
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        except OSError as exc:
            return self._fail_result(f"Cannot read image: {exc}")

        prompt = self._build_qa_prompt(brief, plan, target_dimensions)
        messages = [{"role": "user", "content": prompt}]

        response = await self._call_llm(
            job=job,
            messages=messages,
            step="qa_check",
            max_tokens=1024,
            images=[image_bytes],
        )

        result = self._parse_qa_response(response)

        # Store QA results on the job for operator dashboard
        job.qa_results = result
        await self._session.flush()

        return result

    def _build_qa_prompt(
        self,
        brief: dict[str, Any],
        plan: dict[str, Any],
        dimensions: str,
    ) -> str:
        """Assemble QA prompt with brief and plan context.

        Dana needs to see what was requested (brief) and what was
        planned (Celeste's plan) to judge compliance accurately.
        """
        parts = [
            "QA this composited image against the brief and plan.\n",
            f"Target dimensions: {dimensions}",
            f"Brand: {brief.get('brand_name', 'Unknown')}",
            f"Headline: {brief.get('headline_text', '')}",
        ]

        if brief.get("cta_text"):
            parts.append(f"CTA expected: {brief['cta_text']}")
        if brief.get("brand_colours"):
            parts.append(f"Brand colours: {brief['brand_colours']}")
        if brief.get("restrictions_dont"):
            parts.append(f"Restrictions: {brief['restrictions_dont']}")

        logo_size = plan.get("logo", {}).get("size_proportion", 0.15)
        parts.append(f"Planned logo size: {logo_size:.0%} of canvas width")

        parts.append("\nRun all 3 checks and return JSON results.")

        return "\n".join(parts)

    def _parse_qa_response(self, response: str) -> dict[str, Any]:
        """Extract JSON QA results from Dana's response.

        Falls back to a conservative fail if parsing fails — better
        to flag for review than to pass a bad composition.
        """
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end])
                self._validate_qa_structure(result)
                return result
            except (json.JSONDecodeError, KeyError):
                pass

        return self._fail_result("Could not parse QA response")

    def _validate_qa_structure(self, result: dict[str, Any]) -> None:
        """Ensure all required QA fields exist with correct types.

        Adds missing fields with conservative defaults rather than
        crashing — a partial QA result is better than none.
        """
        for check_key in ("check1_layout", "check2_brief", "check3_spec"):
            if check_key not in result:
                result[check_key] = {"pass": False, "score": 0, "issues": ["Check missing"]}
            check = result[check_key]
            check.setdefault("pass", False)
            check.setdefault("score", 0)
            check.setdefault("issues", [])

        # 2 of 3 checks must pass (not all 3)
        passes = sum(
            1 for k in ("check1_layout", "check2_brief", "check3_spec")
            if result[k]["pass"]
        )
        result.setdefault("overall_pass", passes >= 2)
        result.setdefault("recommendation", "send_to_user" if result["overall_pass"] else "revise_composition")
        result.setdefault("revision_notes", "")

    def _fail_result(self, reason: str) -> dict[str, Any]:
        """Generate a conservative fail result for error cases.

        Used when the image can't be read or the LLM response can't
        be parsed — always safer to fail and review than to pass blindly.
        """
        return {
            "check1_layout": {"pass": False, "score": 0, "issues": [reason]},
            "check2_brief": {"pass": False, "score": 0, "issues": [reason]},
            "check3_spec": {"pass": False, "score": 0, "issues": [reason]},
            "overall_pass": False,
            "recommendation": "escalate",
            "revision_notes": reason,
        }
