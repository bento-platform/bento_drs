from hashlib import sha256

__all__ = [
    "drs_file_checksum",
    "len_zero",
]

CHUNK_SIZE = 16 * 1024


def drs_file_checksum(path: str, chunk_size: int = CHUNK_SIZE) -> str:
    hash_obj = sha256()

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def len_zero(x: list) -> bool:
    return len(x) == 0
