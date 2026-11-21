"""News -> events, using an LLM behind an OpenAI-compatible API (e.g. vLLM on Red Hat OpenShift AI).

The model only proposes events. Every event goes through the same checks as /forecast input (events.py),
plus a check that shift_amount names a real scheduled payment of this account. Rejected events are returned
with a reason instead of being silently dropped.
"""
import json
import re

import httpx

from .config import Settings
from .events import Event, parse_event, unknown_streams
from .schedule import Payment

SYSTEM_PROMPT = """You are the news analyst of an autonomous CFO for a small business.
Read the news item and decide whether it changes the business's cash flow. Reply with JSON only:
{"events": [ ... ]}   (an empty list if the news is irrelevant)

Allowed events (all dates ISO yyyy-mm-dd):
{"type":"shift_amount","stream":<exact payment name from the list>,"from":date,"change_pct":number,"certainty":..,"why":..}
{"type":"one_off","date":date,"amount":number (EUR, negative = money out),"certainty":..,"why":..}
{"type":"scale","flow":"sales"|"costs","from":date,"to":date (optional),"factor_mean":number,"factor_sd":number,"certainty":..,"why":..}
{"type":"closure","from":date,"to":date,"certainty":..,"why":..}

"sales" is variable money in (card sales, customer payments), "costs" is variable money out (suppliers, goods).
Rules: use "official" only when the news states a concrete, enacted change with a date and a rate or amount; otherwise "assumption".
Never invent numbers the news does not support; keep assumptions modest and give them a realistic factor_sd (0 to 0.2).
factor_mean must be between 0.5 and 1.5, change_pct between -50 and 100. Ignore news that has no mechanism to affect this business."""


class LLMError(RuntimeError):
    """The model could not be reached or did not answer with usable JSON."""


def business_context(description: str, schedule: list[Payment], today: str) -> str:
    """Short description of the business and its scheduled payments, sent with every news item."""
    lines = [f"{description or 'Small business'}. EUR account. Today is {today}.",
             "Scheduled payments (exact name: day of month, frequency, EUR per payment, last bank reference):"]
    for p in schedule:
        freq = "every month" if p.months is None else f"months {p.months}"
        lines.append(f'- "{p.name}": day {p.day}, {freq}, {p.amount:,.2f}, "{p.last_reference}"')
    lines.append("Variable cash: everything else (sales in, supplier and goods spend out).")
    return "\n".join(lines)


def ask_llm(settings: Settings, news: str, context: str) -> str:
    """Send one news item to the model and return the text of its reply."""
    if not settings.llm_configured:
        raise LLMError("the news model is not configured (set LLM_BASE_URL and LLM_MODEL)")
    body = {
        "model": settings.llm_model,
        "temperature": 0,
        "max_tokens": settings.llm_max_tokens,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": f"BUSINESS:\n{context}\n\nNEWS:\n{news}"}],
    }
    if settings.llm_json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
    try:
        r = httpx.post(f"{settings.llm_base_url}/chat/completions", json=body, headers=headers,
                       timeout=settings.llm_timeout_s, verify=settings.llm_verify_tls)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"model endpoint answered {exc.response.status_code}: {exc.response.text[:300]}") from exc
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"could not get an answer from the model: {exc}") from exc


def events_from_reply(reply: str, stream_names: set[str]) -> tuple[list[Event], list[dict]]:
    """Model reply -> (accepted events, rejected [{"event": raw, "reason": ...}])."""
    m = re.search(r"\{.*\}", reply, re.S)              # tolerate code fences or words around the JSON
    try:
        raw_events = json.loads(m.group(0))["events"]
        if not isinstance(raw_events, list):
            raise TypeError
    except Exception:
        raise LLMError(f"the model did not reply with JSON containing an 'events' list: {reply[:300]!r}") from None

    accepted, rejected = [], []
    for raw in raw_events:
        try:
            event = parse_event(raw)
        except ValueError as exc:
            rejected.append({"event": raw, "reason": str(exc)})
            continue
        if unknown_streams([event], stream_names):
            rejected.append({"event": raw, "reason": f"unknown scheduled payment {event.stream!r}"})
            continue
        accepted.append(event)
    return accepted, rejected
