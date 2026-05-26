import json
import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

SYSTEM_PROMPT = """
You are a polite AI sales assistant. Keep replies short, natural, and human-like.
Always disclose that this is an automated assistant if asked.
Never pressure the user.
If user says remove me, do not call, stop, wrong number, or not interested, classify correctly.
Ask one question at a time.
Goal is to qualify interest and collect callback time.

Return only valid JSON:
{
  "reply": "short sentence to speak",
  "status": "interested | not_interested | callback | dnc | wrong_number | busy | continue | completed",
  "summary": "short summary"
}
""".strip()


def _fallback_reply(message, status="continue", summary="Fallback response generated because AI JSON was unavailable."):
    return {
        "reply": message,
        "status": status,
        "summary": summary,
    }


def _parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def generate_reply(transcript, lead_info, business_script, ai_behavior_instructions=""):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _fallback_reply(
            "I can help with that. What would be a good callback time?",
            "continue",
            "GROQ_API_KEY is missing, so a local fallback reply was used.",
        )

    client = Groq(api_key=api_key)
    lead_json = json.dumps(dict(lead_info), default=str)
    user_prompt = f"""
Lead info:
{lead_json}

Business script:
{business_script}

Additional AI behavior instructions:
{ai_behavior_instructions}

Conversation transcript:
{transcript}
""".strip()

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        return _fallback_reply(
            "Thanks for sharing. Would you like a quick follow-up call later?",
            "continue",
            f"Groq request failed: {exc}",
        )
    content = completion.choices[0].message.content or "{}"

    try:
        data = _parse_json(content)
    except Exception:
        return _fallback_reply(content, "continue", "AI returned non-JSON response")

    allowed = {"interested", "not_interested", "callback", "dnc", "wrong_number", "busy", "continue", "completed"}
    status = data.get("status", "continue")
    if status not in allowed:
        status = "continue"

    return {
        "reply": str(data.get("reply", "Thanks. What would be a good next step?"))[:500],
        "status": status,
        "summary": str(data.get("summary", ""))[:1000],
    }
