"""The person-ontology — the approved typed layer that steers Graphiti's extraction.

Design rules baked in here (from the wayfinder map's locked decisions):
  * Coarse `Literal` buckets, not free scores — the LLM can apply a 3-way label
    consistently across three years; it cannot pick "6 vs 7" reliably.
  * NO `name` attribute on any entity — `name` is reserved by Graphiti's EntityNode
    (along with uuid, group_id, labels, created_at, summary, attributes, name_embedding).
    The concept's own name is Graphiti's node name; we only add *extra* attributes.
  * Atomic attributes with clear descriptions — this is what reduces cross-year drift.

Runs ALONGSIDE Graphiti's open-ended extraction, so anything the ontology doesn't
name is still captured as a generic Entity.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Entity types  (the "aspects of a self")
# ---------------------------------------------------------------------------

class Struggle(BaseModel):
    """A recurring difficulty or challenge the person is working with."""
    domain: Optional[Literal["emotional", "physical", "relational", "practice"]] = Field(
        None, description="Which area of life this difficulty lives in."
    )
    intensity: Optional[Literal["subtle", "moderate", "strong"]] = Field(
        None, description="How loud/dominant the struggle is in this entry."
    )


class Practice(BaseModel):
    """A contemplative technique or practice the person engages in."""
    technique: Optional[Literal[
        "breath-focus", "body-scan", "metta", "noting", "open-awareness", "other"
    ]] = Field(None, description="The kind of meditation/contemplative technique.")
    setting: Optional[Literal["daily", "retreat", "app", "other"]] = Field(
        None, description="The context the practice happened in."
    )


class EmotionalState(BaseModel):
    """An affective state the person experiences."""
    valence: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description="The felt pleasantness of the state."
    )
    activation: Optional[Literal["high", "low"]] = Field(
        None, description="Energy/arousal level of the state."
    )


class Insight(BaseModel):
    """A realization or shift in understanding — a milestone of change."""
    content: Optional[str] = Field(
        None, description="A short paraphrase of what was realized."
    )
    domain: Optional[str] = Field(
        None, description="What the insight is about (practice, self, a relationship, ...)."
    )


class Relationship(BaseModel):
    """A person or relational dynamic in the person's life."""
    role: Optional[Literal["family", "friend", "teacher", "partner", "colleague", "other"]] = Field(
        None, description="How this person relates to the author."
    )
    quality: Optional[str] = Field(
        None, description="The felt quality of the relationship in this entry."
    )


class Intention(BaseModel):
    """An aspiration, vow, or goal the person holds."""
    content: Optional[str] = Field(None, description="What the person intends/aspires to.")
    domain: Optional[str] = Field(None, description="The area the intention concerns.")


# ---------------------------------------------------------------------------
# Edge types  (how the aspects connect — the verbs of a life)
# ---------------------------------------------------------------------------

class StrugglesWith(BaseModel):
    """The author struggles with a difficulty."""


class Practices(BaseModel):
    """The author engages in a contemplative practice."""


class Experiences(BaseModel):
    """The author experiences an emotional state."""


class Realized(BaseModel):
    """The author arrived at an insight."""


class TriggeredBy(BaseModel):
    """A state or struggle is precipitated by something (a person, a situation)."""


class Addresses(BaseModel):
    """A practice is brought to bear on a struggle."""


class ShiftedTo(BaseModel):
    """One state/struggle gives way to another over time — the transition edge that
    powers 'then vs now'. Graphiti stamps this bi-temporally on its own."""


# ---------------------------------------------------------------------------
# Registries passed to add_episode()
# ---------------------------------------------------------------------------

ENTITY_TYPES = {
    "Struggle": Struggle,
    "Practice": Practice,
    "EmotionalState": EmotionalState,
    "Insight": Insight,
    "Relationship": Relationship,
    "Intention": Intention,
}

EDGE_TYPES = {
    "StrugglesWith": StrugglesWith,
    "Practices": Practices,
    "Experiences": Experiences,
    "Realized": Realized,
    "TriggeredBy": TriggeredBy,
    "Addresses": Addresses,
    "ShiftedTo": ShiftedTo,
}

# Which edge types are allowed between which entity types. The author is first-person
# and shows up as a generic "Entity", so author->concept edges use ("Entity", X).
# NOTE: a starting point — refine after seeing prototype output (drift risks in ticket 06/07).
EDGE_TYPE_MAP = {
    ("Entity", "Struggle"): ["StrugglesWith"],
    ("Entity", "Practice"): ["Practices"],
    ("Entity", "EmotionalState"): ["Experiences"],
    ("Entity", "Insight"): ["Realized"],
    ("Practice", "Struggle"): ["Addresses"],
    ("EmotionalState", "Relationship"): ["TriggeredBy"],
    ("Struggle", "Relationship"): ["TriggeredBy"],
    ("EmotionalState", "Entity"): ["TriggeredBy"],
    ("Struggle", "Struggle"): ["ShiftedTo"],
    ("EmotionalState", "EmotionalState"): ["ShiftedTo"],
    ("Entity", "Entity"): ["StrugglesWith", "Practices", "Experiences", "Realized", "TriggeredBy"],
}
