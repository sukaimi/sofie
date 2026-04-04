"""
Step 1: Brief Parser
Extracts a structured brief from conversational messages using the LLM.
"""

import logging

from backend.schemas import BriefParseResult, BriefSchema
from backend.utils.llm_client import parse_json_response

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Sofie's brief extraction engine. Given a conversation between a user and Sofie (the AI account manager), extract a structured creative brief for image generation.

You must output ONLY a JSON object with this exact schema:

{
  "complete": true or false,
  "brief": {
    "brand": "brand-name",
    "platform": "instagram | facebook | tiktok",
    "dimensions": "WIDTHxHEIGHT",
    "campaign": "campaign name or theme",
    "key_message": "the main message to convey",
    "tone": "mood/tone description",
    "must_include": ["list of required elements"],
    "must_avoid": ["list of things to avoid"],
    "text_overlays": [
      {"text": "headline text", "position": "top-centre", "style": "headline"},
      {"text": "sub text", "position": "bottom-centre", "style": "subhead"}
    ]
  },
  "missing_fields": ["list of fields still needed"],
  "follow_up_question": "question to ask the user to complete the brief, or null"
}

Rules:
- Set "complete": true ONLY when you have: brand, platform, dimensions, key_message, and at least one text_overlay
- If the user hasn't specified dimensions, default to "1080x1080" for Instagram
- If platform is not specified, default to "instagram"
- The follow_up_question should be specific and helpful (e.g. "What headline text would you like on the image?")
- Extract tone from context clues even if not explicitly stated
- Must_include and must_avoid should come from the conversation context

Output ONLY valid JSON. No markdown fences, no explanation."""


async def parse_brief(
    messages: list[dict],
    brand_id: str | None = None,
) -> BriefParseResult:
    """Parse conversation messages into a structured brief.

    Args:
        messages: List of {"role": ..., "content": ...} conversation messages.
        brand_id: Optional brand ID to inject into the brief.

    Returns:
        BriefParseResult with complete flag, brief (if complete), or follow-up question.
    """
    llm_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Extract a brief from this conversation:\n\n"
            + "\n".join(
                f"{'USER' if m['role'] == 'user' else 'SOFIE'}: {m['content']}"
                for m in messages
            ),
        },
    ]

    data = await parse_json_response(llm_messages)

    result = BriefParseResult(
        complete=data.get("complete", False),
        missing_fields=data.get("missing_fields", []),
        follow_up_question=data.get("follow_up_question"),
    )

    if data.get("complete") and data.get("brief"):
        brief_data = data["brief"]
        if brand_id:
            brief_data["brand"] = brand_id
        result.brief = BriefSchema(**brief_data)

    return result
