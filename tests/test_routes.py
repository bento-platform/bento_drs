NON_EXISTENT_ID = '123'


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
