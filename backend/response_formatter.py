# backend/response_formatter.py

from backend.models import EmergencyLevel


_ICONS = {
    EmergencyLevel.RESUSCITATION: "🚨",
    EmergencyLevel.EMERGENCY: "🔴",
    EmergencyLevel.URGENT: "🟠",
    EmergencyLevel.SEMI_URGENT: "🟡",
    EmergencyLevel.NON_URGENT: "🟢",
}


def format_response(answer: str, level: int, label: str, urgency: str) -> str:
    try:
        icon = _ICONS.get(EmergencyLevel(int(level)), "ℹ️")
    except Exception:
        icon = "ℹ️"

    answer = answer or ""
    label = label or "Medical advice"
    urgency = urgency or "Please consult a healthcare professional."

    return f"{icon} **{label}**\n\n{answer}\n\n⏰ {urgency}"