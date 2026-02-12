__all__ = [
    "AUTHZ_URL",
    "DATA_TYPE_PHENOPACKET",
    "DUMMY_PROJECT_ID",
    "DUMMY_DATASET_ID_1",
    "DUMMY_DATASET_ID_2",
    "S3_HOST",
    "S3_PORT",
    "S3_SERVER_URL",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "SQLALCHEMY_DATABASE_URI",
]

AUTHZ_URL = "http://bento-authz.local"
SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

DUMMY_PROJECT_ID = "b1738ea3-6ea7-4f43-a13f-51f4398818c4"
DUMMY_DATASET_ID_1 = "c96aa217-e07d-4d52-8c5c-df03f054fd3d"
DUMMY_DATASET_ID_2 = "a3386b25-c5a6-4d44-ab2b-0cd83d5ebd65"

DATA_TYPE_PHENOPACKET = "phenopacket"

S3_HOST = "127.0.0.1"
S3_PORT = "9000"
S3_SERVER_URL = f"http://{S3_HOST}:{S3_PORT}"
S3_ACCESS_KEY = "test_access_key"
S3_SECRET_KEY = "test_secret_key"
