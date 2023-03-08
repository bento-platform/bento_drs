from typing import List, TypedDict

__all__ = [
    "DRSAccessURLDict",
    "DRSAccessMethodDict",
    "DRSChecksumDict",
    "DRSContentsDict",
    "DRSObjectDict",
]

# TODO: py3.10: new TypedDict required pattern


class _DRSAccessURLDictBase(TypedDict):
    url: str


class DRSAccessURLDict(_DRSAccessURLDictBase, total=False):
    headers: List[str]  # TODO: The schema is very unclear with this


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
    checksums: List[DRSChecksumDict]
    created_time: str
    size: int
    self_uri: str


class _DRSContentsDictBase(TypedDict):
    name: str


class DRSContentsDict(_DRSContentsDictBase, total=False):
    id: str
    drs_uri: str
    contents: List["DRSContentsDict"]


class DRSObjectDict(_DRSObjectDictBase, total=False):
    access_methods: List[DRSAccessMethodDict]
    name: str
    description: str
    updated_time: str
    version: str
    mime_type: str
    contents: List[DRSContentsDict]
    aliases: List[str]
