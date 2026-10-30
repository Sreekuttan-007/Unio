from typing import Generic, TypeVar

from fastapi import Query
from pydantic import Field

from app.core.schema import ApiModel

T = TypeVar("T")


class PageResponse(ApiModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int


class PageParams(ApiModel):
    page: int = Field(0, ge=0)
    size: int = Field(20, ge=1, le=100)

    @property
    def skip(self) -> int:
        return self.page * self.size


def page_params(page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100)) -> PageParams:
    return PageParams(page=page, size=size)
