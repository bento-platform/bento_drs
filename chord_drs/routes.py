import os
from flask import abort, jsonify, url_for, request, send_file
from sqlalchemy.orm.exc import NoResultFound
from chord_drs import __version__
from chord_drs.app import application
from chord_drs.models import DrsObject


SERVICE_TYPE = "ca.c3g.chord:drs:{}".format(__version__)
SERVICE_ID = os.environ.get("SERVICE_ID", SERVICE_TYPE)


def create_drs_uri(host: str, object_id: str):
    return f"drs://{host}/{object_id}"


@application.route("/service-info", methods=["GET"])
def service_info():
    # Spec: https://github.com/ga4gh-discovery/ga4gh-service-info
    return jsonify({
        "id": SERVICE_ID,
        "name": "CHORD Data Repository Service",
        "type": SERVICE_TYPE,
        "description": "Data repository service (based on GA4GH's specs) for a CHORD application.",
        "organization": {
            "name": "C3G",
            "url": "http://c3g.ca"
        },
        "contactUrl": "mailto:simon.chenard2@mcgill.ca",
        "version": "0.1.0"
    })


@application.route('/objects/<string:object_id>', methods=['GET'])
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


@application.route('/objects/<string:object_id>/download', methods=['GET'])
def object_download(object_id):
    try:
        drs_object = DrsObject.query.filter_by(id=object_id).one()
    except NoResultFound:
        return abort(404)

    return send_file(drs_object.location)
