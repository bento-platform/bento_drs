from datetime import datetime
from operator import is_none
from typing import Literal

from pydantic import AnyUrl, BaseModel, Field

from .utils import len_zero

__all__ = [
    "DrsBentoExtension",
    "DrsChecksum",
    "DrsAccessUrl",
    "DrsAccessMethod",
    "DrsBlobResponse",
]


# NOTE: these are Pydantic models for the Bento *IMPLEMENTATION* of DRS, not the entire DRS spec.


class DrsBentoExtension(BaseModel):
    project_id: str | None
    dataset_id: str | None
    data_type: str | None
    public: bool


class DrsChecksum(BaseModel):
    checksum: str = Field(..., min_length=1)
    type: Literal["sha-256"]


class DrsAccessUrl(BaseModel):
    url: AnyUrl


class DrsAccessMethod(BaseModel):
    type: Literal["https", "s3"]
    access_url: DrsAccessUrl

    # TODO: validate HTTPS-only or S3


class DrsBlobResponse(BaseModel):
    # required fields
    id: str = Field(..., min_length=1)
    self_url: AnyUrl  # TODO: validate DRS scheme
    size: int = Field(..., ge=0)
    created_time: datetime
    # optional fields
    name: str = Field(default="", exclude_if=len_zero)
    description: str = Field(default="", exclude_if=len_zero)
    updated_time: datetime | None = Field(default=None, exclude_if=is_none)
    version: str = Field(default="", exclude_if=len_zero)
    mime_type: str = Field(default="", exclude_if=len_zero)
    checksums: list[DrsChecksum] = Field(default_factory=list, exclude_if=len_zero)
    access_methods: list[DrsAccessMethod] = Field(default_factory=list, exclude_if=len_zero)
    # extension field
    bento: DrsBentoExtension | None = Field(default=None, exclude_if=is_none)
