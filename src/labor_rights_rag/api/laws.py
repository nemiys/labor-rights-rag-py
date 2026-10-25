"""GET /laws: the laws in the corpus, with how current each text is."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from labor_rights_rag.api.dependencies import SessionDep
from labor_rights_rag.generation.card import knesset_url, wikisource_url
from labor_rights_rag.generation.messages import CURRENCY_WARNINGS
from labor_rights_rag.parsing.hebrew_year import format_hebrew_year
from labor_rights_rag.persistence.models import Law

router = APIRouter()


class LawSummary(BaseModel):
    id: int  # the Knesset id of the law
    name: str
    validity: str | None  # as the Knesset registry says: in force or not
    last_publication_date: date | None  # the registry's last publication
    last_amendment: str | None  # the year of the last amendment in the text, e.g. 5786 (2025-26)
    last_amendment_label: str | None
    last_amendment_url: str | None  # the amendment as published in Reshumot
    currency_status: str  # ok, ahead, behind or unknown (docs/adr/0003)
    currency_warning: str | None
    text_as_of: date | None  # when the text was fetched
    knesset_url: str
    wikisource_url: str


@router.get("/laws", response_model=list[LawSummary])
async def list_laws(session: SessionDep) -> list[LawSummary]:
    laws = await session.scalars(select(Law).order_by(Law.name))
    return [
        LawSummary(
            id=law.odata_id,
            name=law.name,
            validity=law.validity,
            last_publication_date=law.last_publication_date,
            last_amendment=(
                format_hebrew_year(law.last_amendment_year) if law.last_amendment_year else None
            ),
            last_amendment_label=law.last_amendment_label,
            last_amendment_url=law.last_amendment_url,
            currency_status=law.currency_status,
            currency_warning=CURRENCY_WARNINGS.get(law.currency_status),
            text_as_of=law.fetched_at.date() if law.fetched_at else None,
            knesset_url=knesset_url(law.odata_id),
            wikisource_url=wikisource_url(law.wikisource_title),
        )
        for law in laws
    ]
