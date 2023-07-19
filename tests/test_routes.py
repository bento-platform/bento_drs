import bento_lib
import json
import pytest
import responses

from flask import current_app
from jsonschema import validate
from tests.conftest import AUTHZ_URL, non_existant_dummy_file_path, dummy_file_path
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO


NON_EXISTENT_ID = "123"


def validate_object_fields(data, existing_id=None, with_internal_path=False):
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

    method_types = [method['type'] for method in data["access_methods"]]
    assert "http" in method_types
    if is_minio:
        assert "s3" in method_types
    elif is_local and with_internal_path:
        assert "file" in method_types

    if existing_id:
        assert "id" in data and data["id"] == existing_id


def test_service_info(client):
    res = client.get("/service-info")
    data = res.get_json()

    validate(data, bento_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)


def authz_everything_true(count=1):
    responses.post(f"{AUTHZ_URL}/policy/evaluate", json={"result": [True] * count})


def authz_everything_true_scalar():
    responses.post(f"{AUTHZ_URL}/policy/evaluate", json={"result": True})


def authz_everything_false(count=1):
    responses.post(f"{AUTHZ_URL}/policy/evaluate", json={"result": [False] * count})


def authz_drs_specific_obj(iters=1):
    for _ in range(iters):
        authz_everything_false_scalar()
        authz_everything_true()


def authz_everything_false_scalar():
    responses.post(f"{AUTHZ_URL}/policy/evaluate", json={"result": False})


@responses.activate
def test_object_fail(client):
    authz_everything_true_scalar()
    res = client.get(f"/objects/{NON_EXISTENT_ID}")
    assert res.status_code == 404


@responses.activate
def test_object_fail_forbidden(client):
    authz_everything_false_scalar()
    res = client.get(f"/objects/{NON_EXISTENT_ID}")  # can't know if this exists since we don't have access
    assert res.status_code == 403


@responses.activate
def test_object_download_fail(client):
    authz_everything_true_scalar()
    res = client.get(f"/objects/{NON_EXISTENT_ID}/download")
    assert res.status_code == 404


@responses.activate
def test_object_access_fail(client):
    authz_everything_true_scalar()
    res = client.get(f"/objects/{NON_EXISTENT_ID}/access/no_access")
    assert res.status_code == 404


def _test_object_and_download(client, obj, test_range=False):
    res = client.get(f"/objects/{obj.id}")
    data = res.get_json()

    assert res.status_code == 200
    validate_object_fields(data, existing_id=obj.id)

    # Check that we don't have access via an access ID (since we don't generate them)
    res = client.get(f"/objects/{obj.id}/access/no_access")
    assert res.status_code == 404

    # Download the object
    res = client.get(data["access_methods"][0]["access_url"]["url"])

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

        #  - bytes 100-19999
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-1999"),))
        assert res.status_code == 206
        body = res.get_data(as_text=False)
        assert len(body) == 1900

        # Size is 2455, so these'll run off the end and return the whole thing after 100

        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=100-19999"),))
        assert res.status_code == 206
        body = res.get_data(as_text=False)
        assert len(body) == 2355
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

        # - reversed interval
        res = client.get(data["access_methods"][0]["access_url"]["url"], headers=(("Range", "bytes=4-0"),))
        assert res.status_code == 400


@responses.activate
def test_object_and_download_minio(client_minio, drs_object_minio):
    authz_everything_true_scalar()
    _test_object_and_download(client_minio, drs_object_minio)


@responses.activate
def test_object_and_download_minio_specific_perms(client_minio, drs_object_minio):
    # _test_object_and_download does 3 different accesses
    authz_drs_specific_obj(iters=3)
    _test_object_and_download(client_minio, drs_object_minio)


@responses.activate
def test_object_and_download(client, drs_object):
    authz_everything_true_scalar()
    _test_object_and_download(client, drs_object)


@responses.activate
def test_object_and_download_specific_perms(client, drs_object):
    # _test_object_and_download does 3 different accesses
    authz_drs_specific_obj(iters=3)
    _test_object_and_download(client, drs_object)


@responses.activate
def test_object_and_download_with_ranges(client_local, drs_object):
    authz_everything_true_scalar()
    # Only local backend supports ranges for now
    _test_object_and_download(client_local, drs_object, test_range=True)


@responses.activate
def test_object_with_internal_path(client, drs_object):
    authz_everything_true_scalar()

    res = client.get(f"/objects/{drs_object.id}?internal_path=1")
    data = res.get_json()

    assert res.status_code == 200
    validate_object_fields(data, with_internal_path=True)


@responses.activate
def test_object_with_disabled_internal_path(client, drs_object):
    authz_everything_true_scalar()

    res = client.get(f"/objects/{drs_object.id}?internal_path=0")
    data = res.get_json()

    assert res.status_code == 200
    validate_object_fields(data, with_internal_path=False)


@responses.activate
def test_bundle_and_download(client, drs_bundle):
    authz_everything_true_scalar()

    res = client.get(f"/objects/{drs_bundle.id}")
    data = res.get_json()

    assert res.status_code == 200
    assert "access_methods" not in data  # TODO: there should be access_methods for bundles... although it is spec-opt.
    # issue again with the number of files ingested when ran locally vs travis-ci
    assert "contents" in data and len(data["contents"]) > 0
    assert "name" in data and data["name"] == drs_bundle.name

    assert "checksums" in data and len("checksums") > 0

    assert "created_time" in data
    assert "size" in data
    assert "id" in data and data["id"] == drs_bundle.id

    # jsonify sort alphabetically - makes it that the last element will be
    # an object and not a bundle
    obj = data["contents"][-1]

    # Fetch nested object record by ID
    res = client.get(f"/objects/{obj['id']}")
    assert res.status_code == 200
    nested_obj = res.get_json()

    # Fetch nested object bytes
    res = client.get(nested_obj["access_methods"][0]["access_url"]["url"])
    assert res.status_code == 200
    assert res.content_length == nested_obj["size"]

    # Bundle download is currently unimplemented
    res = client.get(f"/objects/{drs_bundle.id}/download")
    assert res.status_code == 400


@responses.activate
def test_search_bad_query(client, drs_bundle):
    authz_everything_true()

    res = client.get("/search")
    assert res.status_code == 400


@responses.activate
@pytest.mark.parametrize("url", (
    "/search?name=asd",
    "/search?fuzzy_name=asd",
))
def test_search_object_empty(client, drs_bundle, url):
    authz_everything_true(count=len(drs_bundle.objects))

    res = client.get(url)
    data = res.get_json()

    assert res.status_code == 200
    assert len(data) == 0


@responses.activate
@pytest.mark.parametrize("url", (
    "/search?name=alembic.ini",
    "/search?fuzzy_name=mbic",
    "/search?name=alembic.ini&internal_path=1",
    "/search?q=alembic.ini",
    "/search?q=mbic.i",
    "/search?q=alembic.ini&internal_path=1",
))
def test_search_object(client, drs_bundle, url):
    authz_everything_true(count=len(drs_bundle.objects))  # TODO: + 1 once we can search bundles

    res = client.get(url)
    data = res.get_json()
    has_internal_path = "internal_path" in url

    assert res.status_code == 200
    assert len(data) == 1

    validate_object_fields(data[0], with_internal_path=has_internal_path)


@responses.activate
def test_object_ingest_fail_1(client):
    authz_everything_true()
    res = client.post("/private/ingest", data={"wrong_arg": "some_path"})
    assert res.status_code == 400


@responses.activate
def test_object_ingest_fail_2(client):
    authz_everything_true()
    res = client.post("/private/ingest", data={"path": non_existant_dummy_file_path()})
    assert res.status_code == 400


def _ingest_one(client, existing_id=None, params=None):
    res = client.post("/private/ingest", data={"path": dummy_file_path(), **(params or {})})
    data = res.get_json()

    assert res.status_code == 201
    validate_object_fields(data, existing_id=existing_id)

    return data


@responses.activate
def test_object_ingest(client):
    authz_everything_true()
    _ingest_one(client)


@responses.activate
def test_object_ingest_dedup(client):
    authz_everything_true()
    data_1 = _ingest_one(client)

    authz_everything_true()
    data_2 = _ingest_one(client, data_1["id"])

    assert json.dumps(data_1, sort_keys=True) == json.dumps(data_2, sort_keys=True)  # deduplicate is True by default

    # ingest again, but with a different set of permissions
    authz_everything_true()
    data_3 = _ingest_one(client, params={"project_id": "project1"})

    assert data_3["id"] != data_2["id"]
    assert data_3["checksums"][0]["checksum"] == data_2["checksums"][0]["checksum"]


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
    res = client.post("/private/ingest", data={})
    assert res.status_code == 400


@responses.activate
def test_object_ingest_forbidden(client):
    authz_everything_false_scalar()
    res = client.post("/private/ingest", data={})  # invalid body shouldn't be caught until after
    assert res.status_code == 403
