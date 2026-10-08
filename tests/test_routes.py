import json
import os.path
import tempfile
import uuid

import bento_lib
import pytest
from jsonschema import validate

from chord_drs.config import get_config
from chord_drs.constants import DATA_SOURCE_LOCAL, DATA_SOURCE_S3
from tests.authz_mock import authz_drs_specific_obj, authz_everything_false, authz_everything_true
from tests.conftest import dummy_file_path, non_existant_dummy_file_path
from tests.constants import DUMMY_DATASET_ID_1, DUMMY_DATASET_ID_2, DUMMY_PROJECT_ID

NON_EXISTENT_ID = "123"


def validate_object_fields(
    data,
    existing_id: str | None = None,
    with_internal_path: bool = False,
    with_bento_properties: bool = False,
):
    is_local = get_config().service_data_source == DATA_SOURCE_LOCAL
    is_s3 = get_config().service_data_source == DATA_SOURCE_S3

    assert "contents" not in data
    assert "access_methods" in data
    assert len(data["access_methods"]) == 1 if is_local and not with_internal_path else 2
    assert "access_url" in data["access_methods"][0]
    assert "url" in data["access_methods"][0]["access_url"]
    assert "checksums" in data and len("checksums") > 0
    assert "created_time" in data
    assert "size" in data
    assert "self_uri" in data

    method_types = [method["type"] for method in data["access_methods"]]
    assert "https" in method_types
    if is_s3:
        assert "s3" in method_types
    elif is_local and with_internal_path:
        assert "file" in method_types

    if existing_id:
        assert "id" in data and data["id"] == existing_id

    if with_bento_properties:
        assert "bento" in data
        bento_data = data["bento"]
        assert "project_id" in bento_data
        assert "dataset_id" in bento_data
        assert "data_type" in bento_data
        assert "public" in bento_data
    else:
        assert "bento" not in data


def test_service_info(client):
    res = client.get("/service-info")
    data = res.json()
    validate(data, bento_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)

    res = client.get("/ga4gh/drs/v1/service-info")
    data = res.json()
    validate(data, bento_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)


def test_method_not_allowed(client):
    res = client.post("/service-info")
    assert res.status_code == 405


def test_object_fail(client):
    authz_everything_true()

    res = client.get(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 404

    res = client.delete(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 404


def test_object_fail_forbidden(client):
    authz_everything_false()

    res = client.get(f"/objects/{NON_EXISTENT_ID}")  # can't know if this exists since we don't have access
    assert res.status_code == 403

    res = client.delete(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 403


def test_object_download_fail(client):
    authz_everything_true()
    res = client.get(f"/objects/{NON_EXISTENT_ID}/download")
    assert res.status_code == 404


def test_object_access_fail(client):
    authz_everything_true()
    res = client.get(f"/objects/{NON_EXISTENT_ID}/access/no_access")
    assert res.status_code == 404


def _test_object_and_download(client, obj, test_range=False):
    res = client.get(f"/objects/{obj.id}")
    data = res.json()
    assert res.status_code == 200
    validate_object_fields(data, existing_id=obj.id)

    # Check that we can get extra Bento data
    res = client.get(f"/objects/{obj.id}?with_bento_properties=true")
    data = res.json()
    assert res.status_code == 200
    validate_object_fields(data, existing_id=obj.id, with_bento_properties=True)

    # Check that we don't have access via an access ID (since we don't generate them)
    res = client.get(f"/objects/{obj.id}/access/no_access")
    assert res.status_code == 404

    # Download the object
    res = client.get(data["access_methods"][0]["access_url"]["url"])
    assert res.status_code == 200
    assert int(res.headers["content-length"]) == obj.size
    assert len(res.content) == obj.size

    # Download the object (POST)
    res = client.post(data["access_methods"][0]["access_url"]["url"])
    assert res.status_code == 200
    assert int(res.headers["content-length"]) == obj.size
    assert len(res.content) == obj.size

    if test_range:
        # Test fetching with Range headers

        #  - first 5 bytes of a file
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=0-4"),))
        assert res.status_code == 206
        body = res.content
        assert len(body) == 5

        #  - bytes 100-1999
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-1999"),))
        assert res.status_code == 206
        body = res.content
        assert len(body) == 1900

        # Size is 2455, so these'll run off the end and return the whole thing after 100

        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-"),))
        assert res.status_code == 206
        body = res.content
        assert len(body) == 2355

        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=0-"),))
        assert res.status_code == 206
        body = res.content
        assert len(body) == 2455

        # Test range error state

        # - no range, no equals
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes"),))
        assert res.status_code == 400

        # - no range, with equals
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes="),))
        assert res.status_code == 400

        # - typo for bytes
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bites=0-4"),))
        assert res.status_code == 400

        #  - cannot request more than what is available
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-19999"),))
        assert res.status_code == 416

        # - reversed interval
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=4-0"),))
        assert res.status_code == 416


def test_object_and_download_s3(client_s3, drs_object_s3):
    authz_everything_true()
    res = client_s3.get(f"/objects/{drs_object_s3.id}")
    data = res.json()
    assert res.status_code == 200

    res = client_s3.get(data["access_methods"][0]["access_url"]["url"])
    assert res.status_code == 200

    with open(dummy_file_path(), "rb") as fh:
        assert res.content == fh.read()


def test_object_and_download_s3_range(client_s3, drs_object_s3):
    authz_everything_true()
    res = client_s3.get(f"/objects/{drs_object_s3.id}")
    data = res.json()

    res = client_s3.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=0-4"),))
    assert res.status_code == 206
    assert res.content == b"# CHO"  # first five bytes (0-4 inclusive) of dummy_file.txt


def test_object_and_download_s3_specific_perms(client_s3, drs_object_s3):
    # _test_object_and_download does 5 different accesses
    authz_drs_specific_obj(iters=5)
    _test_object_and_download(client_s3, drs_object_s3)


def test_object_and_download(client, drs_object):
    authz_everything_true()
    _test_object_and_download(client, drs_object)


def test_object_and_download_specific_perms(client, drs_object):
    # _test_object_and_download does 5 different accesses
    authz_drs_specific_obj(iters=5)
    _test_object_and_download(client, drs_object)


def test_object_and_download_with_ranges(client_local, drs_object):
    authz_everything_true()
    # Only local backend supports ranges for now
    _test_object_and_download(client_local, drs_object, test_range=True)


def test_object_with_internal_path(client, drs_object):
    authz_everything_true()

    res = client.get(f"/objects/{drs_object.id}?internal_path=1")
    data = res.json()

    assert res.status_code == 200
    validate_object_fields(data, with_internal_path=True)


def test_object_with_disabled_internal_path(client, drs_object):
    authz_everything_true()

    res = client.get(f"/objects/{drs_object.id}?internal_path=0")
    data = res.json()

    assert res.status_code == 200
    validate_object_fields(data, with_internal_path=False)


def test_object_delete(client):
    authz_everything_true()

    contents = str(uuid.uuid4())

    # first, ingest a new object for us to test deleting with
    with tempfile.NamedTemporaryFile(mode="w") as tf:
        tf.write(contents)  # random content, so checksum is unique
        tf.flush()
        res = client.post("/ingest", data={"path": tf.name})

    ingested_obj = res.json()

    res = client.delete(f"/objects/{ingested_obj['id']}")
    assert res.status_code == 204

    # deleted, so if we try again it should be a 404

    res = client.delete(f"/objects/{ingested_obj['id']}")
    assert res.status_code == 404


def test_object_multi_delete(client, session_maker):
    from chord_drs.models import DrsBlob

    authz_everything_true()

    contents = str(uuid.uuid4())

    # first, ingest two new objects with the same contents
    with tempfile.NamedTemporaryFile(mode="w") as tf:
        tf.write(contents)  # random content, so checksum is unique
        tf.flush()

        # two different projects to ensure we have two objects pointing to the same resource:
        res1 = client.post("/ingest", data={"path": tf.name, "project_id": "project1"})
        assert res1.status_code == 201
        res2 = client.post("/ingest", data={"path": tf.name, "project_id": "project2"})
        assert res2.status_code == 201

    i1 = res1.json()
    i2 = res2.json()

    assert i1["id"] != i2["id"]

    with session_maker() as session:
        b1 = session.get(DrsBlob, i1["id"])
        b2 = session.get(DrsBlob, i2["id"])

    assert b1.location == b2.location

    # make sure we can get the bytes of i2
    assert client.get(f"/objects/{i2['id']}/download").status_code == 200

    # delete i2
    rd2 = client.delete(f"/objects/{i2['id']}")
    assert rd2.status_code == 204

    # make sure we can still get the bytes of i1
    assert client.get(f"/objects/{i1['id']}/download").status_code == 200

    # check file exists if local
    if b1.location.startswith("/"):
        assert os.path.exists(b1.location)

    # delete i1
    rd1 = client.delete(f"/objects/{i1['id']}")
    assert rd1.status_code == 204

    # check file doesn't exist if local
    if b1.location.startswith("/"):
        assert not os.path.exists(b1.location)


def test_search_bad_query(client, drs_multi_object):
    authz_everything_true()

    res = client.get("/search")
    assert res.status_code == 400


@pytest.mark.parametrize(
    "url",
    (
        "/search?name=asd",
        "/search?fuzzy_name=asd",
        "/search?fuzzy_name=alembic.ini&data_type=experiment",  # data type wrong
        "/search?data_type=experiment",  # data type wrong
    ),
)
def test_search_object_empty(client, drs_multi_object, url):
    authz_everything_true(count=2)

    res = client.get(url)
    data = res.json()

    assert res.status_code == 200
    assert len(data) == 0


@pytest.mark.parametrize(
    "url,count,n_resources",
    (
        ("/search?name=alembic.ini", 1, 1),
        ("/search?fuzzy_name=mbic", 1, 1),
        ("/search?name=alembic.ini&internal_path=1", 1, 1),
        ("/search?q=alembic.ini", 1, 1),
        ("/search?q=mbic.i", 1, 1),
        ("/search?q=alembic.ini&internal_path=1", 1, 1),
        ("/search?fuzzy_name=.py", 2, 1),  # two objects, same resource (idx 1 and 3)
        (f"/search?dataset={DUMMY_DATASET_ID_1}", 2, 1),  # two objects, same resource (idx 1 and 3)
        (f"/search?dataset={DUMMY_DATASET_ID_1}&dataset={DUMMY_DATASET_ID_2}", 4, 2),  # both datasets, all objects
        (f"/search?fuzzy_name=.py&project={DUMMY_PROJECT_ID}", 2, 1),  # "
        (f"/search?project={DUMMY_PROJECT_ID}", 4, 2),  # all objects are part of the same project, with two datasets
        ("/search?data_type=phenopacket", 4, 2),  # all test objects are have the same data type value
        ("/search?data_type=phenopacket&data_type=experiment", 4, 2),  # no contribution from experiments
        (f"/search?fuzzy_name=.py&project={DUMMY_PROJECT_ID}&dataset={DUMMY_DATASET_ID_2}", 2, 1),  # "
        (f"/search?fuzzy_name=.py&project={DUMMY_PROJECT_ID}&data_type=phenopacket", 2, 1),  # "
        (f"/search?fuzzy_name=.py&project={DUMMY_PROJECT_ID}&dataset={DUMMY_DATASET_ID_1}", 0, 0),  # wrong dataset
        ("/search?fuzzy_name=e", 3, 2),  # three objects, two resources
    ),
)
def test_search_object(client, drs_multi_object, url, count, n_resources):
    authz_everything_true(count=n_resources)

    res = client.get(url)
    data = res.json()
    has_internal_path = "internal_path" in url

    assert res.status_code == 200
    assert len(data) == count

    for obj in data:
        validate_object_fields(obj, with_internal_path=has_internal_path)


def test_search_no_permissions(client, drs_multi_object):
    authz_everything_false(count=len(drs_multi_object))

    res = client.get("/search?name=alembic.ini")
    data = res.json()

    assert res.status_code == 200
    assert len(data) == 0


def test_object_ingest_fail_1(client):
    authz_everything_true()
    res = client.post("/ingest", data={"wrong_arg": "some_path"})
    assert res.status_code == 400


def test_object_ingest_fail_2(client):
    authz_everything_true()
    res = client.post("/ingest", data={"path": non_existant_dummy_file_path()})
    assert res.status_code == 400


@pytest.mark.parametrize("mime_type", ["image/*", "invalid/mime", "text/html;"])
def test_object_ingest_bad_mime_type(client, mime_type: str):
    authz_everything_true()
    res = client.post("/ingest", data={"path": dummy_file_path(), "mime_type": mime_type})
    assert res.status_code == 400
    data = res.json()
    assert data["code"] == 400
    assert data["errors"] == [{"message": "Invalid MIME type"}]


def _ingest_one(client, existing_id=None, params=None):
    res = client.post("/ingest", data={"path": dummy_file_path(), **(params or {})})
    data = res.json()

    assert res.status_code == 201
    validate_object_fields(data, existing_id=existing_id, with_bento_properties=True)

    return data


def test_object_ingest(client):
    authz_everything_true()
    data = _ingest_one(client)
    # check we don't have fields we didn't specify
    assert "description" not in data
    assert "mime_type" not in data


def test_object_ingest_with_mime(client):
    authz_everything_true()
    data = _ingest_one(client, params={"mime_type": "text/plain"})
    assert data["mime_type"] == "text/plain"


def test_object_ingest_dedup(client):
    authz_everything_true()
    data_1 = _ingest_one(client)

    authz_everything_true()
    data_2 = _ingest_one(client, data_1["id"])

    assert json.dumps(data_1, sort_keys=True) == json.dumps(data_2, sort_keys=True)  # deduplicate is True by default

    # ingest again, but with a different set of permissions
    authz_everything_true()
    data_3 = _ingest_one(client, params={"project_id": "project1", "dataset_id": ""})  # dataset_id: "" -> None

    assert data_3["id"] != data_2["id"]
    assert data_3["checksums"][0]["checksum"] == data_2["checksums"][0]["checksum"]

    # bento properties should exist in the ingest response:
    assert data_3["bento"]
    assert data_3["bento"]["project_id"] == "project1"
    assert data_3["bento"]["dataset_id"] is None
    assert data_3["bento"]["data_type"] is None
    assert not data_3["bento"]["public"]


def test_object_ingest_no_deduplicate(client):
    authz_everything_true()
    data_1 = _ingest_one(client)

    authz_everything_true()
    data_2 = _ingest_one(client, params={"deduplicate": False})

    assert json.dumps(data_1, sort_keys=True) != json.dumps(data_2, sort_keys=True)


def test_object_ingest_bad_req(client):
    authz_everything_true()
    res = client.post("/ingest", data={})
    assert res.status_code == 400


def test_object_ingest_forbidden(client):
    authz_everything_false()
    res = client.post("/ingest", data={})  # invalid body shouldn't be caught until after
    assert res.status_code == 403


def test_object_ingest_post_file(client):
    # actual bytes of file in request
    fp = dummy_file_path()
    authz_everything_true()
    with open(fp, "rb") as fh:
        res = client.post("/ingest", files={"file": ("dummy_file.txt", fh)})
    assert res.status_code == 201
    validate_object_fields(res.json(), with_bento_properties=True)
