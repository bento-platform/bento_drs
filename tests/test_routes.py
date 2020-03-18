import chord_lib
from jsonschema import validate
from tests.conftest import NON_EXISTENT_DUMMY_FILE, DUMMY_FILE


NON_EXISTENT_ID = '123'


def validate_object_fields(data, existing_id=None):
    assert "contents" not in data
    assert "access_methods" in data
    assert len(data["access_methods"]) == 1
    assert "access_url" in data["access_methods"][0]
    assert "url" in data["access_methods"][0]["access_url"]

    assert "checksums" in data
    assert "created_time" in data
    assert "size" in data
    assert "self_uri" in data

    if existing_id:
        assert "id" in data and data["id"] == existing_id


def test_service_info(client):
    res = client.get("/service-info")
    data = res.get_json()

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
    validate_object_fields(data, existing_id=drs_object.id)

    # Download the object
    res = client.get(data["access_methods"][0]["access_url"]["url"])

    assert res.status_code == 200
    assert res.content_length == drs_object.size


def test_object_inside_bento(client, drs_object):
    res = client.get(f'/objects/{drs_object.id}', headers={'X-CHORD-Internal': '1'})
    data = res.get_json()

    assert res.status_code == 200
    assert len(data["access_methods"]) == 2


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

    res = client.get(obj["access_methods"][0]["access_url"]["url"])

    assert res.status_code == 200
    assert res.content_length == obj["size"]


def test_object_ingest_fail(client):
    res = client.post('/ingest', json={'wrong_arg': 'some_path'})

    assert res.status_code == 400

    res = client.post('/ingest', json={'path': NON_EXISTENT_DUMMY_FILE})

    assert res.status_code == 400


def test_object_ingest(client):
    res = client.post('/ingest', json={'path': DUMMY_FILE})
    data = res.get_json()

    assert res.status_code == 201
    validate_object_fields(data)
