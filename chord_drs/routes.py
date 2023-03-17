import re
import urllib.parse
import subprocess

from bento_lib.responses import flask_errors
from flask import (
    Blueprint,
    current_app,
    jsonify,
    url_for,
    request,
    send_file,
    make_response
)
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
from typing import List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError

from chord_drs import __version__
from chord_drs.constants import BENTO_SERVICE_KIND, SERVICE_NAME, SERVICE_TYPE
from chord_drs.data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO
from chord_drs.db import db
from chord_drs.models import DrsBlob, DrsBundle
from chord_drs.types import DRSAccessMethodDict, DRSContentsDict, DRSObjectDict
from chord_drs.utils import drs_file_checksum


RE_STARTING_SLASH = re.compile(r"^/")
MIME_OCTET_STREAM = "application/octet-stream"
CHUNK_SIZE = 1024 * 16  # Read 16 KB at a time

drs_service = Blueprint("drs_service", __name__)


def strtobool(val: str):
    return val.lower() in ("yes", "true", "t", "1", "on")


def bad_request_and_log(err: str) -> BadRequest:
    current_app.logger.error(err)
    return BadRequest(err)


def get_drs_base_path():
    base_path = request.host

    if current_app.config["CHORD_URL"]:
        parsed_chord_url = urlparse(current_app.config["CHORD_URL"])
        base_path = f"{parsed_chord_url.netloc}{parsed_chord_url.path}"

        if current_app.config["CHORD_SERVICE_URL_BASE_PATH"]:
            base_path = urljoin(
                base_path, re.sub(
                    RE_STARTING_SLASH, "", current_app.config["CHORD_SERVICE_URL_BASE_PATH"]
                )
            )

    return base_path


def create_drs_uri(object_id: str) -> str:
    return f"drs://{get_drs_base_path()}/{object_id}"


def build_contents(bundle: DrsBundle, inside_container: bool, expand: bool) -> List[DRSContentsDict]:
    content: List[DRSContentsDict] = []
    bundles = DrsBundle.query.filter_by(parent_bundle=bundle).all()

    for b in bundles:
        content.append({
            **({"contents": build_contents(b, inside_container, expand)} if expand else {}),
            "drs_uri": create_drs_uri(b.id),
            "id": b.id,
            "name": b.name,  # TODO: Can overwrite... see spec
        })

    for c in bundle.objects:
        content.append({
            "drs_uri": create_drs_uri(c.id),
            "id": c.id,
            "name": c.name,  # TODO: Can overwrite... see spec
        })

    return content


def build_bundle_json(drs_bundle: DrsBundle, inside_container: bool = False, expand: bool = False) -> DRSObjectDict:
    return {
        "contents": build_contents(drs_bundle, inside_container, expand),
        "checksums": [
            {
                "checksum": drs_bundle.checksum,
                "type": "sha-256",
            },
        ],
        "created_time": f"{drs_bundle.created.isoformat('T')}Z",
        "size": drs_bundle.size,
        "name": drs_bundle.name,
        # Description should be excluded if null in the database
        **({"description": drs_bundle.description} if drs_bundle.description is not None else {}),
        "id": drs_bundle.id,
        "self_uri": create_drs_uri(drs_bundle.id)
    }


def build_blob_json(drs_blob: DrsBlob, inside_container: bool = False) -> DRSObjectDict:
    data_source = current_app.config["SERVICE_DATA_SOURCE"]

    default_access_method: DRSAccessMethodDict = {
        "access_url": {
            # url_for external was giving weird results - build the URL by hand instead using the internal url_for
            "url": urllib.parse.urljoin(urllib.parse.urljoin(
                str(current_app.config["CHORD_URL"]),  # str cast to shut up the IDE type-checker
                current_app.config["CHORD_SERVICE_URL_BASE_PATH"].rstrip("/") + "/",
            ), url_for("drs_service.object_download", object_id=drs_blob.id).lstrip("/"))
            # No headers --> auth will have to be obtained via some
            # out-of-band method, or the object's contents are public. This
            # will depend on how the service is deployed.
        },
        "type": "http",
    }

    access_methods: List[DRSAccessMethodDict] = [default_access_method]

    if inside_container and data_source == DATA_SOURCE_LOCAL:
        access_methods.append({
            "access_url": {
                "url": f"file://{drs_blob.location}",
            },
            "type": "file",
        })
    elif data_source == DATA_SOURCE_MINIO:
        access_methods.append({
            "access_url": {
                "url": drs_blob.location,
            },
            "type": "s3",
        })

    return {
        "access_methods": access_methods,
        "checksums": [
            {
                "checksum": drs_blob.checksum,
                "type": "sha-256",
            },
        ],
        "created_time": f"{drs_blob.created.isoformat('T')}Z",
        "size": drs_blob.size,
        "name": drs_blob.name,
        # Description should be excluded if null in the database
        **({"description": drs_blob.description} if drs_blob.description is not None else {}),
        "id": drs_blob.id,
        "self_uri": create_drs_uri(drs_blob.id)
    }


@drs_service.route("/service-info", methods=["GET"])
def service_info():
    # Spec: https://github.com/ga4gh-discovery/ga4gh-service-info
    info = {
        "id": current_app.config["SERVICE_ID"],
        "name": SERVICE_NAME,
        "type": SERVICE_TYPE,
        "description": "Data repository service (based on GA4GH's specs) for a Bento platform node.",
        "organization": {
            "name": "C3G",
            "url": "https://www.computationalgenomics.ca"
        },
        "contactUrl": "mailto:info@c3g.ca",
        "version": __version__,
        "environment": "prod",
        "bento": {
            "serviceKind": BENTO_SERVICE_KIND,
        },
    }

    if not current_app.config["BENTO_DEBUG"]:
        return jsonify(info)

    info["environment"] = "dev"
    try:
        if res_tag := subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"]):
            res_tag_str = res_tag.decode().rstrip()
            info["git_tag"] = res_tag_str
            info["bento"]["gitTag"] = res_tag_str
        if res_branch := subprocess.check_output(["git", "branch", "--show-current"]):
            res_branch_str = res_branch.decode().strip()
            info["git_branch"] = res_branch_str
            info["bento"]["gitBranch"] = res_branch_str
        if res_commit := subprocess.check_output(["git", "rev-parse", "HEAD"]):
            info["bento"]["gitCommit"] = res_commit.decode().strip()

    except Exception as e:
        except_name = type(e).__name__
        print("Error in dev-mode retrieving git information", except_name, e)

    return jsonify(info)


def get_drs_object(object_id: str) -> Tuple[Optional[Union[DrsBlob, DrsBundle]], bool]:
    if drs_bundle := DrsBundle.query.filter_by(id=object_id).first():
        return drs_bundle, True

    # Only try hitting the database for an object if no bundle was found
    if drs_blob := DrsBlob.query.filter_by(id=object_id).first():
        return drs_blob, False

    return None, False


@drs_service.route("/objects/<string:object_id>", methods=["GET"])
@drs_service.route("/ga4gh/drs/v1/objects/<string:object_id>", methods=["GET"])
def object_info(object_id: str):
    expand = request.args.get("expand") in ("true", "1", "yes")

    drs_object, is_bundle = get_drs_object(object_id)

    if not drs_object:
        raise NotFound("No object found for this ID")

    # Log X-CHORD-Internal header
    current_app.logger.debug(f"object_info X-CHORD-Internal: {request.headers.get('X-CHORD-Internal', 'not set')}")

    # Are we inside the bento singularity container? if so, provide local access method
    inside_container = request.headers.get("X-CHORD-Internal", "0") == "1"
    # The requester can specify object internal path to be added to the response
    use_internal_path = strtobool(request.args.get("internal_path", ""))
    include_internal_path = inside_container or use_internal_path

    if is_bundle:
        return jsonify(build_bundle_json(drs_object, inside_container=include_internal_path, expand=expand))

    return jsonify(build_blob_json(drs_object, inside_container=include_internal_path))


@drs_service.route("/objects/<string:object_id>/access/<string:access_id>", methods=["GET"])
@drs_service.route("/ga4gh/drs/v1/objects/<string:object_id>/access/<string:access_id>", methods=["GET"])
def object_access(object_id: str, access_id: str):
    drs_object, is_bundle = get_drs_object(object_id)

    if not drs_object:
        raise NotFound("No object found for this ID")

    # We explicitly do not support access_id-based accesses; all of them will be 'not found'
    # since we don't provide access IDs

    # TODO: Eventually generate one-time signed URLs or something?

    raise NotFound(f"No access ID '{access_id}' exists for object '{object_id}'")


@drs_service.route("/search", methods=["GET"])
def object_search():
    # TODO: Enable search for bundles too

    response = []

    name = request.args.get("name")
    fuzzy_name = request.args.get("fuzzy_name")
    search_q = request.args.get("q")
    internal_path = request.args.get("internal_path", "")

    if name:
        objects = DrsBlob.query.filter_by(name=name).all()
    elif fuzzy_name:
        objects = DrsBlob.query.filter(DrsBlob.name.contains(fuzzy_name)).all()
    elif search_q:
        objects = DrsBlob.query.filter(or_(
            DrsBlob.id.contains(search_q),
            DrsBlob.name.contains(search_q),
            DrsBlob.checksum.contains(search_q),
            DrsBlob.description.contains(search_q),
        ))
    else:
        raise BadRequest("Missing GET search terms (name | fuzzy_name | q)")

    for obj in objects:
        response.append(build_blob_json(obj, strtobool(internal_path)))

    return jsonify(response)


@drs_service.route("/objects/<string:object_id>/download", methods=["GET"])
def object_download(object_id):
    logger = current_app.logger

    # TODO: Bundle download

    try:
        drs_object = DrsBlob.query.filter_by(id=object_id).one()
    except NoResultFound:
        return flask_errors.flask_not_found_error("No object found for this ID")

    minio_obj = drs_object.return_minio_object()

    if not minio_obj:
        # Check for "Range" HTTP header
        range_header = request.headers.get("Range")  # supports "headers={'Range': 'bytes=x-y'}"

        if range_header is None:
            # Early return, no range header so send the whole thing
            return send_file(
                drs_object.location,
                mimetype=MIME_OCTET_STREAM,
                download_name=drs_object.name,
            )

        logger.debug(f"Found Range header: {range_header}")
        range_err = f"Malformatted range header: expected bytes=X-Y or bytes=X-, got {range_header}"

        rh_split = range_header.split("=")
        if len(rh_split) != 2 or rh_split[0] != "bytes":
            raise bad_request_and_log(range_err)

        byte_range = rh_split[1].strip().split("-")
        logger.debug(f"Retrieving byte range {byte_range}")

        try:
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else None
        except (IndexError, ValueError):
            raise bad_request_and_log(range_err)

        if end is not None and end < start:
            raise bad_request_and_log(f"Invalid range header: end cannot be less than start (start={start}, end={end})")

        def generate_bytes():
            with open(drs_object.location, "rb") as fh2:
                # First, skip over <start> bytes to get to the beginning of the range
                fh2.seek(start)

                # Then, read in either CHUNK_SIZE byte segments or however many bytes are left to send, whichever is
                # left. This avoids filling memory with the contents of large files.
                byte_offset: int = start
                while True:
                    # Add a 1 to the amount to read if it's below chunk size, because the last coordinate is inclusive.
                    data = fh2.read(min(CHUNK_SIZE, (end + 1 - byte_offset) if end is not None else CHUNK_SIZE))
                    byte_offset += len(data)
                    yield data

                    # If we've hit the end of the file and are reading empty byte strings, or we've reached the
                    # end of our range (inclusive), then escape the loop.
                    # This is guaranteed to terminate with a finite-sized file.
                    if len(data) == 0 or (end is not None and byte_offset > end):
                        break

        # Stream the bytes of the file or file segment from the generator function
        r = current_app.response_class(generate_bytes(), status=206, mimetype=MIME_OCTET_STREAM)
        r.headers["Accept-Ranges"] = "bytes"
        r.headers["Content-Disposition"] = \
            f"attachment; filename*=UTF-8'{urllib.parse.quote(drs_object.name, encoding='utf-8')}'"
        return r

    # TODO: Support range headers for MinIO objects - only the local backend supports it for now
    # TODO: kinda greasy, not really sure we want to support such a feature later on
    response = make_response(
        send_file(
            minio_obj["Body"],
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=drs_object.name
        )
    )

    response.headers["Content-length"] = minio_obj["ContentLength"]
    return response


@drs_service.route("/private/ingest", methods=["POST"])
def object_ingest():
    logger = current_app.logger
    data = request.json or {}

    obj_path: str = data.get("path")

    if not obj_path or not isinstance(obj_path, str):
        raise bad_request_and_log(f"Missing or invalid path parameter in JSON request: {obj_path}")

    drs_object: Optional[DrsBlob] = None
    deduplicate: bool = data.get("deduplicate", True)  # Change for v0.9: default to True

    if deduplicate:
        # Get checksum of original file, and query database for objects that match

        try:
            checksum = drs_file_checksum(obj_path)
        except FileNotFoundError:
            raise bad_request_and_log(f"File not found at path {obj_path}")

        drs_object = DrsBlob.query.filter_by(checksum=checksum).first()
        if drs_object:
            logger.info(f"Found duplicate DRS object via checksum (will deduplicate): {drs_object}")

    if not drs_object:
        try:
            drs_object = DrsBlob(location=obj_path)
            db.session.add(drs_object)
            db.session.commit()
            logger.info(f"Added DRS object: {drs_object}")
        except Exception as e:  # TODO: More specific handling
            logger.error(f"Encountered exception during ingest: {e}")
            raise InternalServerError("Error while creating the object")

    response = build_blob_json(drs_object)

    return response, 201
