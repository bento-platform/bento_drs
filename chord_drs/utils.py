from hashlib import sha256


__all__ = ["drs_file_checksum"]

CHUNK_SIZE = 16 * 1024


def drs_file_checksum(path: str) -> str:
    hash_obj = sha256()

    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()
