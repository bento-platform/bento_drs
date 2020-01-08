from flask import abort, jsonify, url_for, request, send_file
from sqlalchemy.orm.exc import NoResultFound
from chord_drs.app import app
from chord_drs.models import DrsObject


def create_drs_uri(host: str, object_id: str):
    return f"drs://{host}/{object_id}"


@app.route('/objects/<string:object_id>', methods=['GET'])
def object_info(object_id):
    try:
        drs_object = DrsObject.query.filter_by(id=object_id).one()
    except NoResultFound:
        return abort(404)

    response = {
        "access_methods": {
            "access_url": {
                "url": url_for('object_download', object_id=drs_object.id, _external=True)
            },
            "type": "https"
        },
        "checksums": {
            "checksum": drs_object.checksum,
            "type": "sha-256"
        },
        "created_time": f"{drs_object.created.isoformat('T')}Z",
        "size": drs_object.size,
        "id": drs_object.id,
        "self_uri": create_drs_uri(request.host, drs_object.id)
    }

    return jsonify(response)


@app.route('/objects/<string:object_id>/download', methods=['GET'])
def object_download(object_id):
    try:
        drs_object = DrsObject.query.filter_by(id=object_id).one()
    except NoResultFound:
        return abort(404)

    return send_file(drs_object.location)
