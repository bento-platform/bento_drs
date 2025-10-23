from typing import NotRequired, TypedDict

__all__ = [
    "DRSAccessURLDict",
    "DRSAccessMethodDict",
    "DRSChecksumDict",
    "DRSObjectBentoDict",
    "DRSObjectDict",
]


class DRSAccessURLDict(TypedDict):
    url: str
    headers: NotRequired[list[str]]  # TODO: The schema is very unclear with this


class DRSAccessMethodDict(TypedDict):
    type: str
    access_id: NotRequired[str]
    access_url: NotRequired[DRSAccessURLDict]
    region: NotRequired[str]


class DRSChecksumDict(TypedDict):
    checksum: str
    type: str


class DRSObjectBentoDict(TypedDict):
    project_id: str | None
    dataset_id: str | None
    data_type: str | None
    public: bool


class DRSObjectDict(TypedDict):
    id: str
    checksums: list[DRSChecksumDict]
    created_time: str
    size: int
    self_uri: str
    # ---
    access_methods: NotRequired[list[DRSAccessMethodDict]]
    name: NotRequired[str]
    description: NotRequired[str]
    updated_time: NotRequired[str]
    version: NotRequired[str]
    mime_type: NotRequired[str]
    aliases: NotRequired[list[str]]
    bento: NotRequired[DRSObjectBentoDict]
