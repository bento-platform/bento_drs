import logging
import os
import re
import tempfile
import urllib.parse

from asgiref.sync import async_to_sync
from bento_lib.auth.permissions import Permission, P_INGEST_DATA, P_QUERY_DATA, P_DELETE_DATA, P_DOWNLOAD_DATA
from bento_lib.auth.resources import RESOURCE_EVERYTHING, build_resource
from bento_lib.service_info.constants import SERVICE_ORGANIZATION_C3G
from bento_lib.service_info.helpers import build_service_info
from bento_lib.streaming.exceptions import StreamingBadRange, StreamingRangeNotSatisfiable
from bento_lib.streaming.range import parse_range_header
from flask import (
    Blueprint,
    Request,
    current_app,
    jsonify,
    request,
    send_file,
    make_response,
)
from sqlalchemy import or_
from werkzeug.exceptions import BadRequest, Forbidden, NotFound, InternalServerError, RequestedRangeNotSatisfiable

from . import __version__
from .authz import authz_middleware
from .backend import get_backend
from .constants import BENTO_SERVICE_KIND, SERVICE_NAME, SERVICE_TYPE, MIME_OCTET_STREAM
from .db import db
from .models import DrsBlob
from .serialization import build_blob_json
from .utils import drs_file_checksum


RE_STARTING_SLASH = re.compile(r"^/")
CHUNK_SIZE = 1024 * 128  # Read 128 KB at a time

drs_service = Blueprint("drs_service", __name__)

build_service_info_sync = async_to_sync(build_service_info)


def str_to_bool(val: str) -> bool:
    return val.lower() in ("yes", "true", "t", "1", "on")


def forbidden() -> Forbidden:
    authz_middleware.mark_authz_done(request)
    return Forbidden()


def authz_enabled() -> bool:
    return current_app.config["AUTHZ_ENABLED"]


def check_everything_permission(permission: Permission) -> bool:
    return authz_middleware.evaluate_one(request, RESOURCE_EVERYTHING, permission) if authz_enabled() else True


def _post_headers_getter(r: Request) -> dict[str, str]:
    token = r.form.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def check_objects_permission(
    drs_objs: list[DrsBlob], permission: Permission, mark_authz_done: bool = False
) -> tuple[bool, ...]:
    if not authz_enabled():
        return tuple([True] * len(drs_objs))  # Assume we have permission for everything if authz disabled

    return tuple(
        r[0] or drs_obj.public
        for r, drs_obj in (
            zip(
                authz_middleware.evaluate(
                    request,
                    [build_resource(drs_obj.project_id, drs_obj.dataset_id, drs_obj.data_type) for drs_obj in drs_objs],
                    [permission],
                    headers_getter=_post_headers_getter if request.method == "POST" else None,
                    mark_authz_done=mark_authz_done,
                ),  # gets us a matrix of len(drs_objs) rows, 1 column with the permission evaluation result
                drs_objs,
            )
        )
    )  # now a tuple of length len(drs_objs) of whether we have the permission for each object


def fetch_and_check_object_permissions(object_id: str, permission: Permission, logger: logging.Logger) -> DrsBlob:
    has_permission_on_everything = check_everything_permission(permission)

    drs_object = get_drs_object(object_id)

    if not drs_object:
        authz_middleware.mark_authz_done(request)
        if authz_enabled() and not has_permission_on_everything:  # Don't leak if this object exists
            logger.error("No object found for the requested ID; masking with 403 to prevent ID discovery")
            raise forbidden()
        raise NotFound("No object found for this ID")

    # Check permissions -------------------------------------------------
    if has_permission_on_everything:
        # Good to go already!
        authz_middleware.mark_authz_done(request)
    else:
        p = check_objects_permission([drs_object], permission, mark_authz_done=True)
        if not p[0]:
            raise forbidden()
    # -------------------------------------------------------------------

    return drs_object


def bad_request_log_mark(err: str) -> BadRequest:
    authz_middleware.mark_authz_done(request)
    current_app.logger.error(err)
    return BadRequest(err)


def range_not_satisfiable_log_mark(description: str, length: int) -> RequestedRangeNotSatisfiable:
    authz_middleware.mark_authz_done(request)
    current_app.logger.error(f"Requested range not satisfiable: {description}; true length: {length}")
    return RequestedRangeNotSatisfiable(description=description, length=length)


@drs_service.route("/service-info", methods=["GET"])
@drs_service.route("/ga4gh/drs/v1/service-info", methods=["GET"])
@authz_middleware.deco_public_endpoint
def service_info():
    # Spec: https://github.com/ga4gh-discovery/ga4gh-service-info
    return jsonify(
        build_service_info_sync(
            {
                "id": current_app.config["SERVICE_ID"],
                "name": SERVICE_NAME,
                "type": SERVICE_TYPE,
                "description": "Data repository service (based on GA4GH's specs) for a Bento platform node.",
                "organization": SERVICE_ORGANIZATION_C3G,
                "contactUrl": "mailto:info@c3g.ca",
                "version": __version__,
                "bento": {
                    "serviceKind": BENTO_SERVICE_KIND,
                },
            },
            debug=current_app.config["BENTO_DEBUG"],
            local=current_app.config["BENTO_CONTAINER_LOCAL"],
            logger=current_app.logger,
        )
    )


def get_drs_object(object_id: str) -> DrsBlob | None:
    return DrsBlob.query.filter_by(id=object_id).first()


def delete_drs_object(object_id: str, logger: logging.Logger):
    drs_object = fetch_and_check_object_permissions(object_id, P_DELETE_DATA, logger)

    logger.info(f"Deleting object {drs_object.id}")

    q = DrsBlob.query.filter_by(location=drs_object.location)
    n_using_file = q.count()
    if n_using_file == 1 and q.first().id == drs_object.id:
        # If this object is the only one using the file, delete the file too
        # TODO: this can create a race condition and leave files undeleted... should we have a cleanup on start?
        logger.info(
            f"Deleting file at {drs_object.location}, since {drs_object.id} is the only object referring to it."
        )
        backend = get_backend()
        backend.delete(drs_object.location)

    db.session.delete(drs_object)
    db.session.commit()


@drs_service.route("/objects/<string:object_id>", methods=["GET", "DELETE"])
@drs_service.route("/ga4gh/drs/v1/objects/<string:object_id>", methods=["GET", "DELETE"])
def object_info(object_id: str):
    logger = current_app.logger

    if request.method == "DELETE":
        delete_drs_object(object_id, logger)
        return current_app.response_class(status=204)

    drs_object = fetch_and_check_object_permissions(object_id, P_QUERY_DATA, logger)

    # The requester can ask for additional, non-spec-compliant Bento properties to be included in the response
    with_bento_properties: bool = str_to_bool(request.args.get("with_bento_properties", ""))

    # The requester can specify object internal path to be added to the response
    use_internal_path: bool = str_to_bool(request.args.get("internal_path", ""))

    return jsonify(
        build_blob_json(drs_object, inside_container=use_internal_path, with_bento_properties=with_bento_properties)
    )


@drs_service.route("/objects/<string:object_id>/access/<string:access_id>", methods=["GET"])
@drs_service.route("/ga4gh/drs/v1/objects/<string:object_id>/access/<string:access_id>", methods=["GET"])
def object_access(object_id: str, access_id: str):
    fetch_and_check_object_permissions(object_id, P_QUERY_DATA, current_app.logger)

    # We explicitly do not support access_id-based accesses; all of them will be 'not found'
    # since we don't provide access IDs

    # TODO: Eventually generate one-time signed URLs or something?

    raise NotFound(f"No access ID '{access_id}' exists for object '{object_id}'")


@drs_service.route("/search", methods=["GET"])
def object_search():
    response = []

    name: str | None = request.args.get("name")
    fuzzy_name: str | None = request.args.get("fuzzy_name")
    search_q: str | None = request.args.get("q")
    internal_path: bool = str_to_bool(request.args.get("internal_path", ""))
    with_bento_properties: bool = str_to_bool(request.args.get("with_bento_properties", ""))

    if name:
        objects = DrsBlob.query.filter_by(name=name).all()
    elif fuzzy_name:
        objects = DrsBlob.query.filter(DrsBlob.name.contains(fuzzy_name)).all()
    elif search_q:
        objects = DrsBlob.query.filter(
            or_(
                DrsBlob.id.contains(search_q),
                DrsBlob.name.contains(search_q),
                DrsBlob.checksum.contains(search_q),
                DrsBlob.description.contains(search_q),
            )
        )
    else:
        authz_middleware.mark_authz_done(request)
        raise BadRequest("Missing GET search terms (name | fuzzy_name | q)")

    # TODO: map objects to resources to avoid duplicate calls to same resource in check_objects_permission
    for obj, p in zip(objects, check_objects_permission(list(objects), P_QUERY_DATA)):
        if p:  # Only include the blob in the search results if we have permissions to view it.
            response.append(build_blob_json(obj, internal_path, with_bento_properties=with_bento_properties))

    authz_middleware.mark_authz_done(request)
    return jsonify(response)


@drs_service.route("/objects/<string:object_id>/download", methods=["GET", "POST"])
def object_download(object_id: str):
    logger = current_app.logger

    drs_object = fetch_and_check_object_permissions(object_id, P_DOWNLOAD_DATA, logger)

    obj_name = drs_object.name
    s3_obj = drs_object.return_s3_object()

    # DRS objects have a nullable mime_type in the database. If mime_type is None, serve the object as a generic
    # application/octet-stream.
    mime_type: str = drs_object.mime_type or MIME_OCTET_STREAM

    if not s3_obj:
        # Check for "Range" HTTP header
        range_header = request.headers.get("Range")  # supports "headers={'Range': 'bytes=x-y'}"

        if range_header is None:
            # Early return, no range header so send the whole thing
            res = make_response(send_file(drs_object.location, mimetype=mime_type, download_name=obj_name))
            res.headers["Accept-Ranges"] = "bytes"
            return res

        obj_size = drs_object.size

        try:
            range_intervals = parse_range_header(range_header, obj_size)
        except StreamingBadRange as e:
            raise bad_request_log_mark(str(e))
        except StreamingRangeNotSatisfiable as e:
            raise range_not_satisfiable_log_mark(str(e), obj_size)

        logger.debug(f"Found valid Range header: {range_header}")

        start, end = range_intervals[0]

        def generate_bytes():
            with open(drs_object.location, "rb") as fh2:
                # First, skip over <start> bytes to get to the beginning of the range
                fh2.seek(start)

                # Then, read in either CHUNK_SIZE byte segments or however many bytes are left to send, whichever is
                # left. This avoids filling memory with the contents of large files.
                byte_offset: int = start
                while True:
                    # Add a 1 to the amount to read if it's below chunk size, because the last coordinate is inclusive.
                    data = fh2.read(min(CHUNK_SIZE, end + 1 - byte_offset))
                    byte_offset += len(data)
                    yield data

                    # If we've hit the end of the file and are reading empty byte strings, or we've reached the
                    # end of our range (inclusive), then escape the loop.
                    # This is guaranteed to terminate with a finite-sized file.
                    if len(data) == 0 or byte_offset > end:
                        break

        # Stream the bytes of the file or file segment from the generator function
        r = current_app.response_class(generate_bytes(), status=206, mimetype=mime_type)
        r.headers["Content-Length"] = str(end + 1 - start)  # byte range is inclusive, so need to add one
        r.headers["Content-Range"] = f"bytes {start}-{end}/{obj_size}"
        r.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8'{urllib.parse.quote(obj_name, encoding='utf-8')}'"
        )
        return r

    # TODO: Support range headers for S3 objects - only the local backend supports it for now
    # TODO: kinda greasy, not really sure we want to support such a feature later on
    response = make_response(send_file(s3_obj["Body"], mimetype=mime_type, as_attachment=True, download_name=obj_name))

    response.headers["Content-Length"] = s3_obj["ContentLength"]
    return response


@drs_service.route("/ingest", methods=["POST"])
def object_ingest():
    logger = current_app.logger
    data = request.form or {}

    deduplicate: bool = str_to_bool(data.get("deduplicate", "true"))  # Change for v0.9: default to True
    obj_path: str | None = data.get("path")
    project_id: str | None = data.get("project_id") or None  # replace blank strings with None
    dataset_id: str | None = data.get("dataset_id") or None  # "
    data_type: str | None = data.get("data_type") or None  # "
    public: bool = data.get("public", "false").strip().lower() == "true"

    file = request.files.get("file")
    mime_type: str | None = data.get("mime_type") or None  # replace blank strings with None

    logger.info(f"Received ingest request metadata: {data}")

    # This authz call determines everything, so we can mark authz as done when the call completes:
    has_permission: bool = (
        authz_middleware.evaluate_one(
            request,
            build_resource(project_id, dataset_id, data_type),
            P_INGEST_DATA,
            mark_authz_done=True,
        )
        if authz_enabled()
        else True
    )

    if not has_permission:
        raise Forbidden("Forbidden")

    if (obj_path is not None and file is not None) or (obj_path is None and file is None):
        raise bad_request_log_mark("Must specify exactly one of path or file contents")

    drs_object: DrsBlob | None = None  # either the new object, or the object to fully reuse
    object_to_copy: DrsBlob | None = None

    tfh, t_obj_path = tempfile.mkstemp(dir=current_app.config["DRS_INGEST_TMP_DIR"])
    try:
        filename: str | None = None  # no override, use path filename if path is specified instead of a file upload
        if file is not None:
            logger.debug(f"ingest - received file object: {file}")
            logger.debug(f"ingest - writing to temporary path: {t_obj_path}")
            file.save(t_obj_path)
            obj_path = t_obj_path
            filename = file.filename  # still may be none, in which case the temporary filename will be used

        if deduplicate:
            # Get checksum of original file, and query database for objects that match

            try:
                checksum = drs_file_checksum(obj_path)
            except FileNotFoundError:
                raise bad_request_log_mark(f"File not found at path {obj_path}")

            # Currently, we require exact permissions compatibility for deduplication of IDs.
            # It might be possible to relax this a bit, but we can't fully relax this for two reasons:
            #  - we would need to keep track of sets of permissions for each DRS object
            #  - certain attacks may be performable by creating a second project/dataset in a semi-public instance
            #    and seeing which files are DRS ID duplicates.
            # However, we can actually deduplicate the files on the filesystem as these are more opaque.

            candidate_drs_object: DrsBlob | None = DrsBlob.query.filter_by(checksum=checksum).first()

            if candidate_drs_object is not None:
                c_project_id = candidate_drs_object.project_id
                c_dataset_id = candidate_drs_object.dataset_id
                c_data_type = candidate_drs_object.data_type
                c_public = candidate_drs_object.public

                if (
                    c_project_id == project_id
                    and c_dataset_id == dataset_id
                    and c_data_type == data_type
                    and c_public == public
                ):
                    logger.info(
                        f"Found duplicate DRS object via checksum (will fully deduplicate): {candidate_drs_object}"
                    )
                    drs_object = candidate_drs_object
                else:
                    logger.info(
                        f"Found duplicate DRS object via checksum (will deduplicate JUST bytes; req resource: "
                        f"({project_id}, {dataset_id}, {data_type}, {public}) vs existing resource: "
                        f"({c_project_id}, {c_dataset_id}, {c_data_type}, {c_public})): "
                        f"{candidate_drs_object}"
                    )
                    object_to_copy = candidate_drs_object

        if not drs_object:
            try:
                drs_object = DrsBlob(
                    **(dict(object_to_copy=object_to_copy) if object_to_copy else dict(location=obj_path)),
                    filename=filename,
                    mime_type=mime_type,
                    project_id=project_id,
                    dataset_id=dataset_id,
                    data_type=data_type,
                    public=public,
                )
                db.session.add(drs_object)
                db.session.commit()
                logger.info(f"Added DRS object: {drs_object}")
            except ValueError as e:
                raise bad_request_log_mark(str(e))
            except Exception as e:  # TODO: More specific handling
                authz_middleware.mark_authz_done(request)
                logger.error(f"Encountered exception during ingest: {e}")
                raise InternalServerError("Error while creating the object")

        return build_blob_json(drs_object, with_bento_properties=True), 201

    finally:
        os.close(tfh)
        os.remove(t_obj_path)
