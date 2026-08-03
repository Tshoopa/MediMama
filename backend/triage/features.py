# backend/triage/features.py

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["mild", "moderate", "severe", "unknown"]


@dataclass
class FeatureValue:
    """Rich feature value that still behaves like a bool.

    __bool__/__eq__ let legacy checks like `if f.burn:` or `f.burn == True`
    keep working while carrying severity and modifier metadata.
    """
    present: bool = False
    severity: Severity = "unknown"
    modifiers: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.present

    def __eq__(self, other) -> bool:
        if isinstance(other, FeatureValue):
            return (
                self.present == other.present
                and self.severity == other.severity
                and self.modifiers == other.modifiers
            )
        if isinstance(other, bool):
            return self.present == other
        return NotImplemented

    def __hash__(self):
        return hash((self.present, self.severity))

    def has_modifier(self, key: str, value) -> bool:
        return self.modifiers.get(key) == value


def _fv() -> FeatureValue:
    return FeatureValue()


@dataclass
class ClinicalFeatures:
    raw_text: str
    text: str
    age_months: int | None = None

    # Fever
    temperature: float | None = None
    has_fever: bool = False
    negated_fever: bool = False

    # General condition
    lethargic: bool = False
    unresponsive: bool = False
    hard_to_wake: bool = False
    very_irritable: bool = False
    poor_feeding: bool = False

    # Systemic / infection context
    gastro_recent: bool = False
    cough: bool = False
    urinary_pain: bool = False
    flank_pain: bool = False
    gross_hematuria: bool = False
    jaundice_or_yellow: bool = False
    severe_or_early_jaundice: bool = False

    # Rash / meningitis / CNS infection
    has_rash: bool = False
    non_blanching_rash: bool = False
    stiff_neck: bool = False
    light_sensitivity: bool = False
    photophobia: bool = False
    spreading_rash: bool = False
    rash_starting_on_face: bool = False
    measles_like_rash: bool = False
    cns_infection_red_flags: bool = False

    # Airway / breathing
    not_breathing: bool = False
    blue_lips: bool = False
    choking_silent: bool = False
    breathing_difficulty: bool = False
    fast_breathing: bool = False
    wheeze: bool = False
    grunting: bool = False
    chest_retractions: bool = False
    stridor_or_noisy_breathing: bool = False
    prolonged_coughing_fit: bool = False
    throat_swelling: bool = False

    # Water submersion / near drowning
    water_submersion: bool = False
    post_submersion_coughing: bool = False

    # Allergy / anaphylaxis
    allergen_exposure: bool = False
    hives: FeatureValue = field(default_factory=_fv)
    widespread_hives: bool = False
    face_lip_tongue_swelling: bool = False
    vomiting_after_allergen: bool = False

    # Dehydration / gastro
    diarrhea: bool = False
    diarrhea_count: int | None = None
    vomiting: bool = False
    vomiting_count: int | None = None
    reduced_urine: bool = False
    no_wet_diapers: bool = False
    sunken_eyes: bool = False
    sunken_fontanelle: bool = False
    no_tears: bool = False
    dry_mouth: bool = False
    not_drinking: bool = False
    refusing_fluids: bool = False
    dehydration_score: int = 0

    # Head injury / trauma
    fall_from_height: FeatureValue = field(default_factory=_fv)
    head_injury: FeatureValue = field(default_factory=_fv)
    vomiting_after_head_injury: bool = False
    drowsy_after_head_injury: bool = False

    # Burns
    burn: FeatureValue = field(default_factory=_fv)
    burn_source: str | None = None
    burn_blister: bool = False
    burn_infected: bool = False
    burn_sensitive_area: bool = False

    # Ingestion / poisoning
    swallowed_battery_or_magnet: bool = False
    swallowed_medicine_or_chemical: bool = False
    swallowed_non_sharp_object: bool = False
    plant_ingestion: bool = False

    # Seizure
    seizure: bool = False
    prolonged_seizure: bool = False

    # Throat / airway swallowing red flags
    sore_throat: bool = False
    drooling: bool = False
    cannot_swallow_saliva: bool = False

    # Pain / surgical red flags
    testicular_pain: bool = False
    severe_abdominal_pain: bool = False
    appendicitis_signs: bool = False
    strangulated_hernia_signs: bool = False
    knees_up: bool = False

    # Headache red flags
    headache: bool = False
    worst_headache: bool = False
    sudden_severe_headache: bool = False

    # Wounds / foreign body / bites
    deep_wound: FeatureValue = field(default_factory=_fv)
    animal_bite: FeatureValue = field(default_factory=_fv)
    eye_injury: bool = False
    foreign_body_nose: FeatureValue = field(default_factory=_fv)
    persistent_nosebleed: bool = False

    # Musculoskeletal
    refusing_weight_bear: bool = False
    sudden_limp: bool = False
    hot_swollen_joint: bool = False

    # Mental health emergencies
    suicidal_ideation: bool = False
    self_harm: bool = False

    # Neurological
    loss_of_consciousness: bool = False

    # Endocrine / DKA
    known_diabetic: bool = False
    fruity_breath: bool = False

    # Neonatal infection
    umbilical_redness_or_discharge: bool = False

    # L4 floor marker for mild medical symptoms
    mild_medical_symptom: bool = False

    # Non-medical / routine low-risk hints
    routine_or_nonmedical: bool = False

    # Canonical field names explicitly negated by _apply_negation_overrides.
    # merge_feature_assist reads this so LLM assist can never override an
    # explicit deterministic negation. Stores canonical names (e.g. "has_rash").
    negated_fields: set[str] = field(default_factory=set)

    debug: dict = field(default_factory=dict)


@dataclass
class RuleResult:
    level: int
    title: str
    message: str
    reason: str