import chord_lib
from jsonschema import validate


NON_EXISTENT_ID = '123'


def test_service_info(client):
    rv = client.get("/service-info")
    data = rv.get_json()

    validate(data, chord_lib.schemas.ga4gh.SERVICE_INFO_SCHEMA)


def test_object_fail(client):
    res = client.get(f'/objects/{NON_EXISTENT_ID}')

    assert res.status_code == 404


def test_object_download_fail(client):
    res = client.get(f'/objects/{NON_EXISTENT_ID}/download')

    assert res.status_code == 404


def test_object_and_download(client, drs_object):
    res = client.get(f'/objects/{drs_object.id}')
    data = res.get_json()

    assert res.status_code == 200
    assert "contents" not in data
    assert "access_methods" in data
    assert "access_url" in data["access_methods"]
    assert "url" in data["access_methods"]["access_url"]

    assert "checksums" in data
    assert "created_time" in data
    assert "size" in data
    assert "id" in data and data["id"] == drs_object.id
    assert "self_uri" in data

    # Download the object
    res = client.get(data["access_methods"]["access_url"]["url"])

    assert res.status_code == 200
    assert res.content_length == drs_object.size


def test_bundle_and_download(client, drs_bundle):
    res = client.get(f'/objects/{drs_bundle.id}')
    data = res.get_json()

    assert res.status_code == 200
    assert "access_methods" not in data
    assert "contents" in data
    assert "name" in data["contents"] and data["contents"]["name"] == drs_bundle.name
    # issue again with the number of files ingested when ran locally vs travis-ci
    assert "contents" in data["contents"] and len(data["contents"]["contents"]) > 0

    assert "checksums" in data
    assert "created_time" in data
    assert "size" in data
    assert "id" in data and data["id"] == drs_bundle.id

    # jsonify sort alphabetically - makes it that the last element will be
    # an object and not a bundle
    obj = data["contents"]["contents"][-1]

    res = client.get(obj["access_methods"]["access_url"]["url"])

    assert res.status_code == 200
    assert res.content_length == obj["size"]
