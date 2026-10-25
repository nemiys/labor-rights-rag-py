"""The verification card: built in code from the database, never by the model.

It lets a person check the answer against the source: the exact words of the section, how
current the text is, and where to read the law on the official site.
"""

from datetime import date
from urllib.parse import quote

from pydantic import BaseModel

from labor_rights_rag.generation.messages import CURRENCY_WARNINGS, DISCLAIMER
from labor_rights_rag.persistence.models import Law
from labor_rights_rag.retrieval.hit import Hit

KNESSET_LAW_URL = (
    "https://main.knesset.gov.il/Activity/Legislation/Laws/Pages/LawPrimary.aspx"
    "?t=lawlaws&st=lawlaws&lawitemid={odata_id}"
)
WIKISOURCE_URL = "https://he.wikisource.org/wiki/{title}"


def knesset_url(odata_id: int) -> str:
    return KNESSET_LAW_URL.format(odata_id=odata_id)


def wikisource_url(title: str) -> str:
    return WIKISOURCE_URL.format(title=quote(title.replace(" ", "_")))


class VerificationCard(BaseModel):
    law: str
    law_id: int  # the Knesset id of the law
    section: str
    part: int
    quote: str  # the words of the law as stored: not what the model wrote
    text_as_of: date | None  # when the text was fetched
    currency_status: str
    currency_warning: str | None
    knesset_url: str  # shown to the person; the system never reads it
    wikisource_url: str
    last_amendment: str | None
    last_amendment_url: str | None  # the amendment as published in Reshumot
    search_hint: str
    disclaimer: str


def build_card(hit: Hit, law: Law) -> VerificationCard:
    return VerificationCard(
        law=law.name,
        law_id=law.odata_id,
        section=hit.section_number,
        part=hit.chunk_index,
        quote=hit.text,
        text_as_of=law.fetched_at.date() if law.fetched_at else None,
        currency_status=law.currency_status,
        currency_warning=CURRENCY_WARNINGS.get(law.currency_status),
        knesset_url=knesset_url(law.odata_id),
        wikisource_url=wikisource_url(law.wikisource_title),
        last_amendment=law.last_amendment_label,
        last_amendment_url=law.last_amendment_url,
        search_hint=f"בעמוד החוק, חפשו את סעיף {hit.section_number}.",
        disclaimer=DISCLAIMER,
    )
