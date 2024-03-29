import os
import re
import tempfile
import urllib.parse

from asgiref.sync import async_to_sync
from bento_lib.auth.permissions import Permission, P_INGEST_DATA, P_QUERY_DATA, P_DOWNLOAD_DATA
from bento_lib.auth.resources import RESOURCE_EVERYTHING, build_resource
from bento_lib.service_info.constants import SERVICE_ORGANIZATION_C3G
from bento_lib.service_info.helpers import build_service_info
from flask import (
    Blueprint,
    Request,
    current_app,
    jsonify,
    url_for,
    request,
    send_file,
    make_response,
)
from sqlalchemy import or_
from urllib.parse import urlparse
from werkzeug.exceptions import BadRequest, Forbidden, NotFound, InternalServerError, RequestedRangeNotSatisfiable

from . import __version__
from .authz import authz_middleware
from .constants import BENTO_SERVICE_KIND, SERVICE_NAME, SERVICE_TYPE
from .data_sources import DATA_SOURCE_LOCAL, DATA_SOURCE_MINIO
from .db import db
from .models import DrsBlob, DrsBundle
from .types import DRSAccessMethodDict, DRSContentsDict, DRSObjectDict
from .utils import drs_file_checksum


RE_STARTING_SLASH = re.compile(r"^/")
MIME_OCTET_STREAM = "application/octet-stream"
CHUNK_SIZE = 1024 * 16  # Read 16 KB at a time

drs_service = Blueprint("drs_service", __name__)


def str_to_bool(val: str) -> bool:
    return val.lower() in ("yes", "true", "t", "1", "on")


def forbidden() -> Forbidden:
    authz_middleware.mark_authz_done(request)
    return Forbidden()


def authz_enabled() -> bool:
    return current_app.config["AUTHZ_ENABLED"]


def check_everything_permission(permission: Permission) -> bool:
    return authz_middleware.evaluate_one(request, RESOURCE_EVERYTHING, permission) if authz_enabled() else True


def check_objects_permission(
    drs_objs: list[DrsBlob | DrsBundle], permission: Permission, mark_authz_done: bool = False
) -> tuple[bool, ...]:
    if not authz_enabled():
        return tuple([True] * len(drs_objs))  # Assume we have permission for everything if authz disabled

    def _post_headers_getter(r: Request) -> dict[str, str]:
        token = r.form.get("token")
        return {"Authorization": f"Bearer {token}"} if token else {}

    return tuple(r[0] or drs_obj.public for r, drs_obj in (
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
    ))  # now a tuple of length len(drs_objs) of whether we have the permission for each object


def fetch_and_check_object_permissions(object_id: str, permission: Permission) -> tuple[DrsBlob | DrsBundle, bool]:
    view_data_everything = check_everything_permission(permission)

    drs_object, is_bundle = get_drs_object(object_id)

    if not drs_object:
        authz_middleware.mark_authz_done(request)
        if authz_enabled() and not view_data_everything:  # Don't leak if this object exists
            raise forbidden()
        raise NotFound("No object found for this ID")

    # Check permissions -------------------------------------------------
    if view_data_everything:
        # Good to go already!
        authz_middleware.mark_authz_done(request)
    else:
        p = check_objects_permission([drs_object], permission, mark_authz_done=True)
        if not p[0]:
            raise forbidden()
    # -------------------------------------------------------------------

    return drs_object, is_bundle


def bad_request_log_mark(err: str) -> BadRequest:
    authz_middleware.mark_authz_done(request)
    current_app.logger.error(err)
    return BadRequest(err)


def range_not_satisfiable_log_mark(description: str, length: int) -> RequestedRangeNotSatisfiable:
    authz_middleware.mark_authz_done(request)
    current_app.logger.error(f"Requested range not satisfiable: {description}; true length: {length}")
    return RequestedRangeNotSatisfiable(description=description, length=length)


def get_drs_base_path() -> str:
    parsed_service_url = urlparse(current_app.config["SERVICE_BASE_URL"])
    return f"{parsed_service_url.netloc}{parsed_service_url.path}"


def create_drs_uri(object_id: str) -> str:
    return f"drs://{get_drs_base_path()}/{object_id}"


def build_contents(bundle: DrsBundle, expand: bool) -> list[DRSContentsDict]:
    content: list[DRSContentsDict] = []
    bundles = DrsBundle.query.filter_by(parent_bundle=bundle).all()

    for b in bundles:
        content.append({
            **({"contents": build_contents(b, expand)} if expand else {}),
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


def build_bundle_json(drs_bundle: DrsBundle, expand: bool = False) -> DRSObjectDict:
    return {
        "contents": build_contents(drs_bundle, expand),
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

    blob_url: str = urllib.parse.urljoin(
        current_app.config["SERVICE_BASE_URL"] + "/",
        url_for("drs_service.object_download", object_id=drs_blob.id).lstrip("/")
    )

    https_access_method: DRSAccessMethodDict = {
        "access_url": {
            # url_for external was giving weird results - build the URL by hand instead using the internal url_for
            "url": blob_url,
            # No headers --> auth will have to be obtained via some
            # out-of-band method, or the object's contents are public. This
            # will depend on how the service is deployed.
        },
        "type": "https",
    }

    access_methods: list[DRSAccessMethodDict] = [https_access_method]

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
@drs_service.route("/ga4gh/drs/v1/service-info", methods=["GET"])
@authz_middleware.deco_public_endpoint
def service_info():
    # Spec: https://github.com/ga4gh-discovery/ga4gh-service-info
    return jsonify(async_to_sync(build_service_info)(
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
    ))


def get_drs_object(object_id: str) -> tuple[DrsBlob | DrsBundle | None, bool]:
    if drs_bundle := DrsBundle.query.filter_by(id=object_id).first():
        return drs_bundle, True

    # Only try hitting the database for an object if no bundle was found
    if drs_blob := DrsBlob.query.filter_by(id=object_id).first():
        return drs_blob, False

    return None, False


@drs_service.route("/objects/<string:object_id>", methods=["GET"])
@drs_service.route("/ga4gh/drs/v1/objects/<string:object_id>", methods=["GET"])
def object_info(object_id: str):
    drs_object, is_bundle = fetch_and_check_object_permissions(object_id, P_QUERY_DATA)

    if is_bundle:
        expand: bool = str_to_bool(request.args.get("expand", ""))
        return jsonify(build_bundle_json(drs_object, expand=expand))

    # The requester can specify object internal path to be added to the response
    use_internal_path: bool = str_to_bool(request.args.get("internal_path", ""))
    return jsonify(build_blob_json(drs_object, inside_container=use_internal_path))


@drs_service.route("/objects/<string:object_id>/access/<string:access_id>", methods=["GET"])
@drs_service.route("/ga4gh/drs/v1/objects/<string:object_id>/access/<string:access_id>", methods=["GET"])
def object_access(object_id: str, access_id: str):
    fetch_and_check_object_permissions(object_id, P_QUERY_DATA)

    # We explicitly do not support access_id-based accesses; all of them will be 'not found'
    # since we don't provide access IDs

    # TODO: Eventually generate one-time signed URLs or something?

    raise NotFound(f"No access ID '{access_id}' exists for object '{object_id}'")


@drs_service.route("/search", methods=["GET"])
def object_search():
    # TODO: Enable search for bundles too

    response = []

    name: str | None = request.args.get("name")
    fuzzy_name: str | None = request.args.get("fuzzy_name")
    search_q: str | None = request.args.get("q")
    internal_path: bool = str_to_bool(request.args.get("internal_path", ""))

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
        authz_middleware.mark_authz_done(request)
        raise BadRequest("Missing GET search terms (name | fuzzy_name | q)")

    # TODO: map objects to resources to avoid duplicate calls to same resource in check_objects_permission
    for obj, p in zip(objects, check_objects_permission(list(objects), P_QUERY_DATA)):
        if p:  # Only include the blob in the search results if we have permissions to view it.
            response.append(build_blob_json(obj, internal_path))

    authz_middleware.mark_authz_done(request)
    return jsonify(response)


@drs_service.route("/objects/<string:object_id>/download", methods=["GET", "POST"])
def object_download(object_id: str):
    logger = current_app.logger

    # TODO: Bundle download

    drs_object, is_bundle = fetch_and_check_object_permissions(object_id, P_DOWNLOAD_DATA)

    if is_bundle:
        raise BadRequest("Bundle download is currently unsupported")

    minio_obj = drs_object.return_minio_object()

    if not minio_obj:
        # Check for "Range" HTTP header
        range_header = request.headers.get("Range")  # supports "headers={'Range': 'bytes=x-y'}"

        if range_header is None:
            # Early return, no range header so send the whole thing
            res = make_response(
                send_file(drs_object.location, mimetype=MIME_OCTET_STREAM, download_name=drs_object.name))
            res.headers["Accept-Ranges"] = "bytes"
            return res

        drs_end_byte = drs_object.size - 1

        logger.debug(f"Found Range header: {range_header}")
        range_err = f"Malformatted range header: expected bytes=X-Y or bytes=X-, got {range_header}"

        rh_split = range_header.split("=")
        if len(rh_split) != 2 or rh_split[0] != "bytes":
            raise bad_request_log_mark(range_err)

        byte_range = rh_split[1].strip().split("-")
        logger.debug(f"Retrieving byte range {byte_range}")

        try:
            start: int = int(byte_range[0])
            end: int = int(byte_range[1]) if byte_range[1] else drs_end_byte
        except (IndexError, ValueError):
            raise bad_request_log_mark(range_err)

        if end > drs_end_byte:
            raise range_not_satisfiable_log_mark(
                f"End cannot be past last byte ({end} > {drs_end_byte})",
                drs_object.size)

        if end < start:
            raise range_not_satisfiable_log_mark(
                f"Invalid range header: end cannot be less than start (start={start}, end={end})",
                drs_object.size)

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
                    if len(data) == 0 or byte_offset > end:
                        break

        # Stream the bytes of the file or file segment from the generator function
        r = current_app.response_class(generate_bytes(), status=206, mimetype=MIME_OCTET_STREAM)
        r.headers["Content-Length"] = (end + 1 - start)  # byte range is inclusive, so need to add one
        r.headers["Content-Range"] = f"bytes {start}-{end}/{drs_object.size}"
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

    response.headers["Content-Length"] = minio_obj["ContentLength"]
    return response


@drs_service.route("/ingest", methods=["POST"])
def object_ingest():
    # TODO: Enable specifying a parent bundle
    # TODO: If a parent is specified, make sure we have permissions to ingest into it? How to reconcile?

    logger = current_app.logger
    data = request.form or {}

    deduplicate: bool = str_to_bool(data.get("deduplicate", "true"))  # Change for v0.9: default to True
    obj_path: str | None = data.get("path")
    project_id: str | None = data.get("project_id")
    dataset_id: str | None = data.get("dataset_id")
    data_type: str | None = data.get("data_type")
    public: bool = data.get("public", "false").strip().lower() == "true"
    file = request.files.get("file")

    # This authz call determines everything, so we can mark authz as done when the call completes:
    has_permission: bool = authz_middleware.evaluate_one(
        request,
        build_resource(project_id, dataset_id, data_type),
        P_INGEST_DATA,
        mark_authz_done=True,
    ) if authz_enabled() else True

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
                if all((
                    candidate_drs_object.project_id == project_id,
                    candidate_drs_object.dataset_id == dataset_id,
                    candidate_drs_object.data_type == data_type,
                    candidate_drs_object.public == public,
                )):
                    logger.info(
                        f"Found duplicate DRS object via checksum (will fully deduplicate): {candidate_drs_object}")
                    drs_object = candidate_drs_object
                else:
                    logger.info(
                        f"Found duplicate DRS object via checksum (will deduplicate JUST bytes): "
                        f"{candidate_drs_object}")
                    object_to_copy = candidate_drs_object

        if not drs_object:
            try:
                drs_object = DrsBlob(
                    **(dict(object_to_copy=object_to_copy) if object_to_copy else dict(location=obj_path)),
                    filename=filename,
                    project_id=project_id,
                    dataset_id=dataset_id,
                    data_type=data_type,
                    public=public,
                )
                db.session.add(drs_object)
                db.session.commit()
                logger.info(f"Added DRS object: {drs_object}")
            except Exception as e:  # TODO: More specific handling
                authz_middleware.mark_authz_done(request)
                logger.error(f"Encountered exception during ingest: {e}")
                raise InternalServerError("Error while creating the object")

        return build_blob_json(drs_object), 201

    finally:
        os.close(tfh)
        os.remove(t_obj_path)
