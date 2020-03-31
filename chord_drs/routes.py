import os
import re
import sys

from chord_lib.responses import flask_errors
from flask import Blueprint, abort, current_app, jsonify, url_for, request, send_file
from sqlalchemy.orm.exc import NoResultFound
from typing import Optional
from urllib.parse import urljoin, urlparse

from chord_drs.app import db
from chord_drs.constants import SERVICE_NAME, SERVICE_TYPE
from chord_drs.models import DrsObject, DrsBundle


RE_STARTING_SLASH = re.compile(r"^/")


SERVICE_ID = os.environ.get("SERVICE_ID", SERVICE_TYPE)

drs_service = Blueprint("drs_service", __name__)


def get_drs_base_path():
    base_path = request.host
    if current_app.config["CHORD_URL"]:
        parsed_chord_url = urlparse(current_app.config["CHORD_URL"])
        base_path = f"{parsed_chord_url.netloc}{parsed_chord_url.path}"
        if current_app.config["CHORD_SERVICE_URL_BASE_PATH"]:
            base_path = urljoin(base_path, re.sub(RE_STARTING_SLASH, "",
                                                  current_app.config["CHORD_SERVICE_URL_BASE_PATH"]))
    return base_path


def create_drs_uri(object_id: str) -> str:
    return f"drs://{get_drs_base_path()}/{object_id}"


def build_bundle_json(drs_bundle: DrsBundle, inside_container: Optional[bool] = False) -> dict:
    content = []
    bundles = DrsBundle.query.filter_by(parent_bundle=drs_bundle).all()

    for bundle in bundles:
        obj_json = build_bundle_json(bundle, inside_container=inside_container)
        content.append(obj_json)

    for child in drs_bundle.objects:
        obj_json = build_object_json(child, inside_container=inside_container)
        content.append(obj_json)

    response = {
        "contents": {
            "contents": content,
            "name": drs_bundle.name
        },
        "checksums": {
            "checksum": drs_bundle.checksum,
            "type": "sha-256"
        },
        "created_time": f"{drs_bundle.created.isoformat('T')}Z",
        "size": drs_bundle.size,
        "description": drs_bundle.description,
        "id": drs_bundle.id,
        "self_uri": create_drs_uri(drs_bundle.id)
    }

    return response


def build_object_json(drs_object: DrsObject, inside_container: Optional[bool] = False) -> dict:
    # TODO: This access type is wrong in the case of http (non-secure)

    default_access_method = {
        "access_url": {
            "url": url_for('drs_service.object_download', object_id=drs_object.id, _external=True)
        },
        "type": "https"
    }

    if inside_container:
        access_methods = [
            default_access_method,
            {
                "access_url": {
                    "url": f"file://{drs_object.location}"
                },
                "type": "file"
            }
        ]
    else:
        access_methods = [default_access_method]

    response = {
        "access_methods": access_methods,
        "checksums": {
            "checksum": drs_object.checksum,
            "type": "sha-256"
        },
        "created_time": f"{drs_object.created.isoformat('T')}Z",
        "size": drs_object.size,
        "name": drs_object.name,
        "description": drs_object.description,
        "id": drs_object.id,
        "self_uri": create_drs_uri(drs_object.id)
    }

    return response


@drs_service.route("/service-info", methods=["GET"])
def service_info():
    # Spec: https://github.com/ga4gh-discovery/ga4gh-service-info
    return jsonify({
        "id": SERVICE_ID,
        "name": SERVICE_NAME,
        "type": SERVICE_TYPE,
        "description": "Data repository service (based on GA4GH's specs) for a CHORD application.",
        "organization": {
            "name": "C3G",
            "url": "http://c3g.ca"
        },
        "contactUrl": "mailto:simon.chenard2@mcgill.ca",
        "version": "0.1.0"
    })


@drs_service.route('/objects/<string:object_id>', methods=['GET'])
def object_info(object_id):
    drs_object = DrsObject.query.filter_by(id=object_id).first()
    drs_bundle = DrsBundle.query.filter_by(id=object_id).first()

    if not drs_object and not drs_bundle:
        return abort(404)

    # Are we inside the bento singularity container? if so, provide local accessmethod
    inside_container = request.headers.get("X-CHORD-Internal", "0") == "1"

    # Log X-CHORD-Internal header
    print(f"[{SERVICE_NAME}] object_info X-CHORD-Internal: {request.headers.get('X-CHORD-Internal', 'not set')}",
          flush=True)

    if drs_bundle:
        response = build_bundle_json(drs_bundle, inside_container=inside_container)
    else:
        response = build_object_json(drs_object, inside_container=inside_container)

    return jsonify(response)


@drs_service.route('/search', methods=['GET'])
def object_search():
    response = []
    name = request.args.get('name', None)

    if name:
        # if it includes a dot, we do a strict search.
        if '.' in name:
            objects = DrsObject.query.filter_by(name=name).all()
        else:
            objects = DrsObject.query.filter(DrsObject.name.contains(name)).all()

        for obj in objects:
            response.append(build_object_json(obj))

        return jsonify(response)
    else:
        raise abort(400, description="Missing name param to perform the search")


@drs_service.route('/objects/<string:object_id>/download', methods=['GET'])
def object_download(object_id):
    try:
        drs_object = DrsObject.query.filter_by(id=object_id).one()
    except NoResultFound:
        return abort(404)

    return send_file(drs_object.location)


@drs_service.route('/ingest', methods=['POST'])
def object_ingest():
    try:
        data = request.json
        obj_path = data['path']
    except KeyError:
        return flask_errors.flask_bad_request_error("Missing path parameter in JSON request")

    try:
        new_object = DrsObject(location=obj_path)

        db.session.add(new_object)
        db.session.commit()
    except Exception as e:  # TODO: More specific handling
        print(f"[{SERVICE_NAME}] Encountered exception during ingest: {e}", flush=True, file=sys.stderr)
        return flask_errors.flask_bad_request_error("Error while creating the object")

    response = build_object_json(new_object)

    return response, 201
