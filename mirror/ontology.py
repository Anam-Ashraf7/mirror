"""The person-ontology — the approved typed layer that steers Graphiti's extraction.

Design rules baked in here (from the wayfinder map's locked decisions):
  * Coarse `Literal` buckets, not free scores — the LLM can apply a 3-way label
    consistently across three years; it cannot pick "6 vs 7" reliably.
  * NO `name` attribute on any entity — `name` is reserved by Graphiti's EntityNode
    (along with uuid, group_id, labels, created_at, summary, attributes, name_embedding).
    The concept's own name is Graphiti's node name; we only add *extra* attributes.
  * Atomic attributes with clear descriptions — this is what reduces cross-year drift.

The docstrings here are not decoration: Graphiti feeds each entity/edge docstring straight
into the extraction prompt, so they are written as EXTRACTION RULES with concrete triggers.
This is what makes a weak/cheap model (e.g. gpt-5.4-nano) reliably create EmotionalState /
Struggle / Insight / Intention nodes instead of folding them into free text.

Runs ALONGSIDE Graphiti's open-ended extraction, so anything the ontology doesn't
name is still captured as a generic Entity.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Entity types  (the "aspects of a self")
# ---------------------------------------------------------------------------

class Struggle(BaseModel):
    """A recurring inner difficulty the person wrestles with or is working on in themselves.
    Extract whenever the writer names something they find hard about their own mind/behaviour:
    e.g. holding anger, impatience, difficulty empathising, avoiding vulnerability by lying,
    restlessness in practice, self-criticism. This is a persistent challenge, distinct from a
    momentary feeling (which is an EmotionalState)."""
    domain: Optional[Literal["emotional", "physical", "relational", "practice"]] = Field(
        None, description="Which area of life this difficulty lives in."
    )
    intensity: Optional[Literal["subtle", "moderate", "strong"]] = Field(
        None, description="How loud/dominant the struggle is in this entry."
    )


class Practice(BaseModel):
    """A contemplative or meditative practice/technique the person engages in — e.g. meditation,
    breath-focus, body-scan, metta, noting, remembrance. Extract the practice itself as a node
    (the act of practising is the `Practices` edge)."""
    technique: Optional[Literal[
        "breath-focus", "body-scan", "metta", "noting", "open-awareness", "other"
    ]] = Field(None, description="The kind of meditation/contemplative technique.")
    setting: Optional[Literal["daily", "retreat", "app", "other"]] = Field(
        None, description="The context the practice happened in."
    )


class EmotionalState(BaseModel):
    """A NAMED FEELING or affective state the person experiences — e.g. anger, annoyance, peace,
    contentment, lightness, connection, restlessness, joy, sadness. ALWAYS create a distinct
    node for each named feeling; NEVER fold a feeling into another node's description. A feeling
    is momentary (contrast Struggle, which is a lasting difficulty)."""
    valence: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description="The felt pleasantness of the state."
    )
    activation: Optional[Literal["high", "low"]] = Field(
        None, description="Energy/arousal level of the state."
    )


class Insight(BaseModel):
    """A realization, lesson, or shift in understanding the writer arrives at — usually phrased
    'I realized…', 'I understood…', 'I learned…', 'I saw that…'. Capture the core realization as
    its own node. These are the milestones of change the whole journal exists to track."""
    content: Optional[str] = Field(
        None, description="A short paraphrase of what was realized."
    )
    domain: Optional[str] = Field(
        None, description="What the insight is about (practice, self, a relationship, ...)."
    )


class Relationship(BaseModel):
    """A specific NAMED PERSON in the writer's life (family member, teacher, friend, partner,
    named individual). Extract named people here. Do not extract bare kinship words unless a
    specific person is meant."""
    role: Optional[Literal["family", "friend", "teacher", "partner", "colleague", "other"]] = Field(
        None, description="How this person relates to the author."
    )
    quality: Optional[str] = Field(
        None, description="The felt quality of the relationship in this entry."
    )


class Intention(BaseModel):
    """An aspiration, resolution, vow, or goal the person holds — e.g. 'smile more',
    'listen deeply', 'speak less', 'stay in constant remembrance', 'be more patient'. Capture
    each intention as its own node (the holding of it is the `Intends` edge)."""
    content: Optional[str] = Field(None, description="What the person intends/aspires to.")
    domain: Optional[str] = Field(None, description="The area the intention concerns.")


# ---------------------------------------------------------------------------
# Edge types  (how the aspects connect — the verbs of a life)
# ---------------------------------------------------------------------------

class StrugglesWith(BaseModel):
    """The author struggles with / wrestles with a Struggle."""


class Practices(BaseModel):
    """The author engages in a Practice."""


class Experiences(BaseModel):
    """The author feels / experiences an EmotionalState."""


class Realized(BaseModel):
    """The author arrived at / realized an Insight."""


class TriggeredBy(BaseModel):
    """An EmotionalState or Struggle was precipitated/triggered by a person or situation."""


class Addresses(BaseModel):
    """A Practice is brought to bear on / helps with a Struggle."""


class Intends(BaseModel):
    """The author holds / aspires to an Intention."""


class ShiftedTo(BaseModel):
    """One state/struggle gives way to another over time — the transition edge that
    powers 'then vs now'. Graphiti stamps this bi-temporally on its own."""


# ---------------------------------------------------------------------------
# Extraction guidance — injected into BOTH node and edge extraction prompts via
# add_episode(custom_extraction_instructions=...). This is the second lever (besides the
# docstrings above) for recall + killing open-vocabulary edge drift on cheap models.
# ---------------------------------------------------------------------------

CUSTOM_EXTRACTION_INSTRUCTIONS = """\
This text is a personal meditation-journal entry; the first-person "I/me/my" is the author.

THE SUBJECT IS ALWAYS THE AUTHOR. Create a single node named "Anam" for the author, and make
Anam the owner/experiencer of every feeling, struggle, insight, and intention. Even when the
entry is addressed to someone ("Dear Master, ...") or describes what happened during practice,
it is ANAM who feels, struggles, realizes, and intends — never attribute the author's inner
experience to the person being addressed. "Master" (or "Dear Master") is the teacher/addressee,
NOT the experiencer; do not make Master practice, feel, or realize anything.

Extract GENEROUSLY and consistently — these notes are compared across years, so nothing
recurring should be missed:
- Every NAMED FEELING becomes its own EmotionalState node (anger, annoyance, peace,
  contentment, lightness, connection, restlessness). Never merge a feeling into other text.
- Every RECURRING INNER DIFFICULTY becomes a Struggle node (holding anger, impatience,
  difficulty empathising, avoiding vulnerability).
- Every REALIZATION or lesson ("I realized/understood/learned…") becomes an Insight node.
- Every ASPIRATION or resolution ("smile more", "listen deeply", "speak less") becomes an
  Intention node.
- Named people become Relationship entities.

For relationships between entities, use ONLY these types, and follow the DIRECTION exactly
(the arrow points source -> target):
- Anam -> StrugglesWith -> Struggle          (Anam owns the struggle)
- Anam -> Practices -> Practice               (Anam does the practice)
- Anam -> Experiences -> EmotionalState       (Anam feels the emotion)
- Anam -> Realized -> Insight                 (Anam had the realization)
- Anam -> Intends -> Intention                (Anam holds the aspiration)
- EmotionalState -> TriggeredBy -> Relationship/person   (a feeling is caused BY a person)
- Struggle -> TriggeredBy -> Relationship/person         (a struggle is caused BY a person)
- Practice -> Addresses -> Struggle            (a practice helps WITH a struggle)
- EmotionalState -> ShiftedTo -> EmotionalState (an earlier feeling gives way to a later one)

Do NOT reverse these (e.g. never "person -> TriggeredBy -> feeling", never
"Struggle -> Addresses -> Practice"). Do NOT invent new relation names. If a connection does
not fit one of these types, do not create an edge for it. When the author feels something
toward a person, model it as an EmotionalState Anam Experiences, TriggeredBy that person —
not as a direct edge from Anam to the person.
"""


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
    "Intends": Intends,
    "ShiftedTo": ShiftedTo,
}

# Which edge types are allowed between which entity types. The author is first-person and
# shows up as a generic "Entity", so author->concept edges use ("Entity", X). Every pair we
# care about is mapped, so the model always has a valid TYPED option and needn't freelance a
# name (the #1 source of drift on cheap models).
EDGE_TYPE_MAP = {
    ("Entity", "Struggle"): ["StrugglesWith"],
    ("Entity", "Practice"): ["Practices"],
    ("Entity", "EmotionalState"): ["Experiences"],
    ("Entity", "Insight"): ["Realized"],
    ("Entity", "Intention"): ["Intends"],
    ("Practice", "Struggle"): ["Addresses"],
    ("EmotionalState", "Relationship"): ["TriggeredBy"],
    ("EmotionalState", "Entity"): ["TriggeredBy"],
    ("Struggle", "Relationship"): ["TriggeredBy"],
    ("Struggle", "Entity"): ["TriggeredBy"],
    ("Struggle", "Struggle"): ["ShiftedTo"],
    ("EmotionalState", "EmotionalState"): ["ShiftedTo"],
    ("Entity", "Entity"): [
        "StrugglesWith", "Practices", "Experiences", "Realized", "TriggeredBy", "Intends",
    ],
}
