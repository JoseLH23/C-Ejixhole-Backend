from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CampaignObjective = Literal[
    "atraer_visitas",
    "impulsar_reservas",
    "llenar_hospedaje",
    "promover_camping",
    "informar",
    "reactivar_clientes",
]
MarketingChannel = Literal[
    "facebook",
    "instagram",
    "instagram_story",
    "whatsapp_status",
    "google_business",
]
OfferFocus = Literal["entrada", "camping", "hospedaje", "experiencia_general"]


class CampaignBriefIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=120)
    objective: CampaignObjective
    audience: str = Field(min_length=3, max_length=240)
    main_emotion: str = Field(min_length=3, max_length=80)
    offer_focus: OfferFocus
    season: str = Field(min_length=2, max_length=80)
    channels: list[MarketingChannel] = Field(min_length=1, max_length=5)
    call_to_action: str = Field(
        default="Consulta la información vigente y solicita tu reservación en el portal oficial.",
        min_length=10,
        max_length=240,
    )


class MarketingStatusOut(BaseModel):
    configured: bool
    available: bool
    warming_up: bool = False
    knowledge_version: str | None = None
    documents: int = 0
    message: str


class ChannelContentOut(BaseModel):
    channel: MarketingChannel
    headline: str
    body: str
    call_to_action: str
    hashtags: list[str]


class MarketingCampaignOut(BaseModel):
    name: str
    objective: CampaignObjective
    audience: str
    main_emotion: str
    offer_focus: OfferFocus
    season: str
    knowledge_version: str
    knowledge_document_ids: list[str]
    knowledge_citations: list[str]
    requires_human_approval: bool
    dynamic_facts_used: list[str]
    contents: list[ChannelContentOut]
