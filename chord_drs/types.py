from typing import TypedDict

__all__ = [
    "DRSAccessURLDict",
    "DRSAccessMethodDict",
    "DRSChecksumDict",
    "DRSObjectBentoDict",
    "DRSObjectDict",
]

# TODO: py3.11: new TypedDict required pattern


class _DRSAccessURLDictBase(TypedDict):
    url: str


class DRSAccessURLDict(_DRSAccessURLDictBase, total=False):
    headers: list[str]  # TODO: The schema is very unclear with this


class _DRSAccessMethodDictBase(TypedDict):
    type: str


class DRSAccessMethodDict(_DRSAccessMethodDictBase, total=False):
    access_id: str
    access_url: DRSAccessURLDict
    region: str


class DRSChecksumDict(TypedDict):
    checksum: str
    type: str


class _DRSObjectDictBase(TypedDict):
    id: str
    checksums: list[DRSChecksumDict]
    created_time: str
    size: int
    self_uri: str


class _DRSContentsDictBase(TypedDict):
    name: str


class DRSObjectBentoDict(TypedDict):
    project_id: str | None
    dataset_id: str | None
    data_type: str | None
    public: bool


class DRSObjectDict(_DRSObjectDictBase, total=False):
    access_methods: list[DRSAccessMethodDict]
    name: str
    description: str
    updated_time: str
    version: str
    mime_type: str
    aliases: list[str]
    bento: DRSObjectBentoDict
