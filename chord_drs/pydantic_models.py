from datetime import datetime
from functools import partial
from operator import is_
from typing import Literal, Self

from pydantic import AnyUrl, BaseModel, Field, FileUrl, HttpUrl, UrlConstraints, model_validator

from .utils import len_zero

__all__ = [
    "DrsUri",
    "DrsBentoExtension",
    "DrsChecksum",
    "DrsAccessUrl",
    "DrsAccessMethod",
    "DrsBlobResponse",
    "S3Url",
]


# NOTE: these are Pydantic models for the Bento *IMPLEMENTATION* of DRS, not the entire DRS spec.

is_none = partial(is_, None)


class DrsUri(AnyUrl):
    _constraints = UrlConstraints(host_required=True, allowed_schemes=["drs"])


class S3Url(AnyUrl):
    _constraints = UrlConstraints(allowed_schemes=["s3"])


class DrsBentoExtension(BaseModel):
    project_id: str | None
    dataset_id: str | None
    data_type: str | None
    public: bool


class DrsChecksum(BaseModel):
    checksum: str = Field(..., min_length=64, max_length=64)
    type: Literal["sha-256"]


class DrsAccessUrl(BaseModel):
    url: FileUrl | HttpUrl | S3Url


class DrsAccessMethod(BaseModel):
    type: Literal["file", "https", "s3"]
    access_url: DrsAccessUrl

    @model_validator(mode="after")
    def validate_scheme_matches_type(self) -> Self:
        if self.type != self.access_url.url.scheme and not (
            self.type == "https" and self.access_url.url.scheme == "http"
        ):
            # slightly looser than DRS spec; allow unencrypted HTTP URLs to be access urls
            raise ValueError("access method URL scheme does not match type")
        return self


class DrsBlobResponse(BaseModel):
    # required fields
    id: str = Field(..., min_length=1)
    self_uri: DrsUri
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
