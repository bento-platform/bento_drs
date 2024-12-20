import bento_lib
import json
import os.path
import pytest
import responses
import tempfile
import uuid

from flask import current_app
from jsonschema import validate
from tests.conftest import AUTHZ_URL, non_existant_dummy_file_path, dummy_file_path
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO


NON_EXISTENT_ID = "123"


def validate_object_fields(
    data,
    existing_id: bool = None,
    with_internal_path: bool = False,
    with_bento_properties: bool = False,
):
    is_local = current_app.config["SERVICE_DATA_SOURCE"] == DATA_SOURCE_LOCAL
    is_minio = current_app.config["SERVICE_DATA_SOURCE"] == DATA_SOURCE_MINIO

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
    if is_minio:
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
    from chord_drs.app import application

    res = client.get("/service-info")
    data = res.get_json()
    validate(data, bento_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)

    res = client.get("/ga4gh/drs/v1/service-info")
    data = res.get_json()
    validate(data, bento_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)

    application.config["BENTO_DEBUG"] = True

    res = client.get("/service-info")
    data = res.get_json()
    validate(data, bento_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)


def test_method_not_allowed(client):
    res = client.post("/service-info")
    assert res.status_code == 405


def authz_everything_true(count=1):
    responses.post(f"{AUTHZ_URL}/policy/evaluate", json={"result": [[True] for _ in range(count)]})


def authz_everything_false(count=1):
    responses.post(f"{AUTHZ_URL}/policy/evaluate", json={"result": [[False] for _ in range(count)]})


def authz_drs_specific_obj(iters=1):
    for _ in range(iters):
        authz_everything_false()
        authz_everything_true()


@responses.activate
def test_object_fail(client):
    authz_everything_true()

    res = client.get(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 404

    res = client.delete(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 404


@responses.activate
def test_object_fail_forbidden(client):
    authz_everything_false()

    res = client.get(f"/objects/{NON_EXISTENT_ID}")  # can't know if this exists since we don't have access
    assert res.status_code == 403

    res = client.delete(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 403


@responses.activate
def test_object_download_fail(client):
    authz_everything_true()
    res = client.get(f"/objects/{NON_EXISTENT_ID}/download")
    assert res.status_code == 404


@responses.activate
def test_object_access_fail(client):
    authz_everything_true()
    res = client.get(f"/objects/{NON_EXISTENT_ID}/access/no_access")
    assert res.status_code == 404


def _test_object_and_download(client, obj, test_range=False):
    res = client.get(f"/objects/{obj.id}")
    data = res.get_json()
    assert res.status_code == 200
    validate_object_fields(data, existing_id=obj.id)

    # Check that we can get extra Bento data
    res = client.get(f"/objects/{obj.id}?with_bento_properties=true")
    data = res.get_json()
    assert res.status_code == 200
    validate_object_fields(data, existing_id=obj.id, with_bento_properties=True)

    # Check that we don't have access via an access ID (since we don't generate them)
    res = client.get(f"/objects/{obj.id}/access/no_access")
    assert res.status_code == 404

    # Download the object
    res = client.get(data["access_methods"][0]["access_url"]["url"])
    assert res.status_code == 200
    assert res.content_length == obj.size
    assert len(res.get_data(as_text=False)) == obj.size

    # Download the object (POST)
    res = client.post(data["access_methods"][0]["access_url"]["url"])
    assert res.status_code == 200
    assert res.content_length == obj.size
    assert len(res.get_data(as_text=False)) == obj.size

    if test_range:
        # Test fetching with Range headers

        #  - first 5 bytes of a file
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=0-4"),))
        assert res.status_code == 206
        body = res.get_data(as_text=False)
        assert len(body) == 5

        #  - bytes 100-1999
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-1999"),))
        assert res.status_code == 206
        body = res.get_data(as_text=False)
        assert len(body) == 1900

        # Size is 2455, so these'll run off the end and return the whole thing after 100

        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-"),))
        assert res.status_code == 206
        body = res.get_data(as_text=False)
        assert len(body) == 2355

        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=0-"),))
        assert res.status_code == 206
        body = res.get_data(as_text=False)
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


@responses.activate
def test_object_and_download_minio(client_minio, drs_object_minio):
    authz_everything_true()
    _test_object_and_download(client_minio, drs_object_minio)


@responses.activate
def test_object_and_download_minio_specific_perms(client_minio, drs_object_minio):
    # _test_object_and_download does 5 different accesses
    authz_drs_specific_obj(iters=5)
    _test_object_and_download(client_minio, drs_object_minio)


@responses.activate
def test_object_and_download(client, drs_object):
    authz_everything_true()
    _test_object_and_download(client, drs_object)


@responses.activate
def test_object_and_download_specific_perms(client, drs_object):
    # _test_object_and_download does 5 different accesses
    authz_drs_specific_obj(iters=5)
    _test_object_and_download(client, drs_object)


@responses.activate
def test_object_and_download_with_ranges(client_local, drs_object):
    authz_everything_true()
    # Only local backend supports ranges for now
    _test_object_and_download(client_local, drs_object, test_range=True)


@responses.activate
def test_object_with_internal_path(client, drs_object):
    authz_everything_true()

    res = client.get(f"/objects/{drs_object.id}?internal_path=1")
    data = res.get_json()

    assert res.status_code == 200
    validate_object_fields(data, with_internal_path=True)


@responses.activate
def test_object_with_disabled_internal_path(client, drs_object):
    authz_everything_true()

    res = client.get(f"/objects/{drs_object.id}?internal_path=0")
    data = res.get_json()

    assert res.status_code == 200
    validate_object_fields(data, with_internal_path=False)


@responses.activate
def test_object_delete(client):
    authz_everything_true()

    contents = str(uuid.uuid4())

    # first, ingest a new object for us to test deleting with
    with tempfile.NamedTemporaryFile(mode="w") as tf:
        tf.write(contents)  # random content, so checksum is unique
        tf.flush()
        res = client.post("/ingest", data={"path": tf.name})

    ingested_obj = res.get_json()

    res = client.delete(f"/objects/{ingested_obj['id']}")
    assert res.status_code == 204

    # deleted, so if we try again it should be a 404

    res = client.delete(f"/objects/{ingested_obj['id']}")
    assert res.status_code == 404


@responses.activate
def test_object_multi_delete(client):
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

    i1 = res1.get_json()
    i2 = res2.get_json()

    assert i1["id"] != i2["id"]

    b1 = DrsBlob.query.filter_by(id=i1["id"]).first()
    b2 = DrsBlob.query.filter_by(id=i2["id"]).first()

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


@responses.activate
def test_search_bad_query(client, drs_multi_object):
    authz_everything_true()

    res = client.get("/search")
    assert res.status_code == 400


@responses.activate
@pytest.mark.parametrize(
    "url",
    (
        "/search?name=asd",
        "/search?fuzzy_name=asd",
    ),
)
def test_search_object_empty(client, drs_multi_object, url):
    authz_everything_true(count=len(drs_multi_object))

    res = client.get(url)
    data = res.get_json()

    assert res.status_code == 200
    assert len(data) == 0


@responses.activate
@pytest.mark.parametrize(
    "url",
    (
        "/search?name=alembic.ini",
        "/search?fuzzy_name=mbic",
        "/search?name=alembic.ini&internal_path=1",
        "/search?q=alembic.ini",
        "/search?q=mbic.i",
        "/search?q=alembic.ini&internal_path=1",
    ),
)
def test_search_object(client, drs_multi_object, url):
    authz_everything_true(count=len(drs_multi_object))

    res = client.get(url)
    data = res.get_json()
    has_internal_path = "internal_path" in url

    assert res.status_code == 200
    assert len(data) == 1

    validate_object_fields(data[0], with_internal_path=has_internal_path)


@responses.activate
def test_search_no_permissions(client, drs_multi_object):
    authz_everything_false(count=len(drs_multi_object))

    res = client.get("/search?name=alembic.ini")
    data = res.get_json()

    assert res.status_code == 200
    assert len(data) == 0


@responses.activate
def test_object_ingest_fail_1(client):
    authz_everything_true()
    res = client.post("/ingest", data={"wrong_arg": "some_path"})
    assert res.status_code == 400


@responses.activate
def test_object_ingest_fail_2(client):
    authz_everything_true()
    res = client.post("/ingest", data={"path": non_existant_dummy_file_path()})
    assert res.status_code == 400


@pytest.mark.parametrize("mime_type", ["image/*", "invalid/mime", "text/html;"])
@responses.activate
def test_object_ingest_bad_mime_type(client, mime_type: str):
    authz_everything_true()
    res = client.post("/ingest", data={"path": dummy_file_path(), "mime_type": mime_type})
    assert res.status_code == 400
    data = res.get_json()
    assert data["code"] == 400
    assert data["errors"] == [{"message": "400 Bad Request: Invalid MIME type"}]


def _ingest_one(client, existing_id=None, params=None):
    res = client.post("/ingest", data={"path": dummy_file_path(), **(params or {})})
    data = res.get_json()

    assert res.status_code == 201
    validate_object_fields(data, existing_id=existing_id, with_bento_properties=True)

    return data


@responses.activate
def test_object_ingest(client):
    authz_everything_true()
    data = _ingest_one(client)
    # check we don't have fields we didn't specify
    assert "description" not in data
    assert "mime_type" not in data


@responses.activate
def test_object_ingest_with_mime(client):
    authz_everything_true()
    data = _ingest_one(client, params={"mime_type": "text/plain"})
    assert data["mime_type"] == "text/plain"


@responses.activate
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


@responses.activate
def test_object_ingest_no_deduplicate(client):
    authz_everything_true()
    data_1 = _ingest_one(client)

    authz_everything_true()
    data_2 = _ingest_one(client, params={"deduplicate": False})

    assert json.dumps(data_1, sort_keys=True) != json.dumps(data_2, sort_keys=True)


@responses.activate
def test_object_ingest_bad_req(client):
    authz_everything_true()
    res = client.post("/ingest", data={})
    assert res.status_code == 400


@responses.activate
def test_object_ingest_forbidden(client):
    authz_everything_false()
    res = client.post("/ingest", data={})  # invalid body shouldn't be caught until after
    assert res.status_code == 403


@responses.activate
def test_object_ingest_post_file(client):
    # actual bytes of file in request
    fp = dummy_file_path()
    authz_everything_true()
    with open(fp, "rb") as fh:
        res = client.post("/ingest", data={"file": (fh, "dummy_file.txt")}, content_type="multipart/form-data")
    assert res.status_code == 201
    validate_object_fields(res.get_json(), with_bento_properties=True)
