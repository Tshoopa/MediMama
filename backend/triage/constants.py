# backend/triage/constants.py

LABELS = {
    1: (
        "Resuscitation",
        "This is a life-threatening emergency. CALL 000/911 IMMEDIATELY.",
    ),
    2: (
        "Emergency",
        "This needs urgent medical evaluation. Go to the nearest emergency department.",
    ),
    3: (
        "Urgent",
        "See a doctor or visit an urgent care clinic today.",
    ),
    4: (
        "Semi-Urgent",
        "Schedule an appointment with a GP within 1-2 days. Monitor at home.",
    ),
    5: (
        "Non-Urgent",
        "Monitor at home. See a doctor if symptoms worsen.",
    ),
}

# Legacy thresholds — direct red-flag semantic backup is currently
# disabled in semantic_backup.py. Kept for reference / potential rollback.
L1_RED_FLAG_THRESHOLD = 0.72
L2_RED_FLAG_THRESHOLD = 0.62
NON_EMERGENCY_THRESHOLD = 0.42

CRITICAL_TOPICS = {
    "Button battery safety",
    "Meningitis",
    "Poisoning prevention",
    "Choking prevention",
    "Water safety",
}

EMERGENCY_TOPICS = {
    "Swallowed objects",
    "Head injury",
    "Burns and scalds",
    "Pneumonia",
    "Asthma",
    "Dehydration",
    "Allergic reactions",
    "Rashes",
}

EVIDENCE_DANGER_SIGNS = [
    "refer urgently",
    "danger sign",
    "hospital immediately",
    "call an ambulance",
    "life-threatening",
    "call 000",
    "non-blanching",
]