import asyncio
import os
import shutil
import tempfile
import urllib.parse
from collections.abc import Callable
from typing import Annotated

import orjson
from bento_lib.auth.middleware.fastapi import FastApiAuthMiddleware
from bento_lib.auth.permissions import P_DELETE_DATA, P_DOWNLOAD_DATA, P_INGEST_DATA, P_QUERY_DATA, Permission
from bento_lib.auth.resources import RESOURCE_EVERYTHING, build_resource
from bento_lib.streaming.exceptions import StreamingBadRange, StreamingException, StreamingRangeNotSatisfiable
from bento_lib.streaming.range import parse_range_header
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BeforeValidator
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from .authz import AuthzMiddlewareDep
from .backend import get_backend
from .config import ConfigDep
from .constants import MIME_OCTET_STREAM
from .db import SessionDep
from .logger import logger
from .models import DrsBlob
from .pydantic_models import DrsBlobResponse
from .serialization import build_blob_response
from .utils import drs_file_checksum

__all__ = ["drs_router"]

drs_router = APIRouter()


def str_to_bool(val: str) -> bool:
    return val.lower() in ("yes", "true", "t", "1", "on")


# Boolean query/form parameter which, like in the pre-FastAPI versions of this service, treats any unrecognized value
# (including a blank one) as false rather than as a validation error.
LenientBool = Annotated[bool, BeforeValidator(lambda v: str_to_bool(v) if isinstance(v, str) else v)]

HeadersGetter = Callable[[Request], dict[str, str]]


def attachment_header(filename: str) -> dict[str, str]:
    """
    Constructs a Content-Disposition header for responding with a file as an attachment.
    """
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename, encoding='utf-8')}"}


def resource_from_object(drs_obj: DrsBlob) -> dict:
    """
    Constructs a Bento authorization resource dictionary from a DRS blob record.
    """
    return build_resource(drs_obj.project_id, drs_obj.dataset_id, drs_obj.data_type)


def resources_from_objects(drs_objs: list[DrsBlob]) -> tuple[dict[str, int], list[dict]]:
    """
    Constructs a map of DRS ID --> index of resource in returned resource list for fast deduplicated permissions
    evaluations on multiple DRS objects. Skips any public DRS objects so we don't waste time with lookups we don't need,
    as public objects are a free-for-all.
    """

    id_resource_map: dict[str, int] = {}
    resource_idx_map: dict[bytes, int] = {}
    resources_dedup: list[dict] = []

    for drs_obj, resource in zip(drs_objs, map(resource_from_object, drs_objs)):
        rk = orjson.dumps(resource, option=orjson.OPT_SORT_KEYS)
        resource_idx = resource_idx_map.get(rk)
        if resource_idx is None:
            new_idx = len(resources_dedup)
            id_resource_map[drs_obj.id] = new_idx
            resource_idx_map[rk] = new_idx
            resources_dedup.append(resource)
        else:
            id_resource_map[drs_obj.id] = resource_idx

    return id_resource_map, resources_dedup


async def check_everything_permission(authz: FastApiAuthMiddleware, request: Request, permission: Permission) -> bool:
    return await authz.async_evaluate_one(request, RESOURCE_EVERYTHING, permission) if authz.enabled else True


async def check_objects_permission(
    authz: FastApiAuthMiddleware,
    request: Request,
    drs_objs: list[DrsBlob],
    permission: Permission,
    mark_authz_done: bool = False,
    headers_getter: HeadersGetter | None = None,
) -> tuple[bool, ...]:
    if not authz.enabled:
        return tuple([True] * len(drs_objs))  # Assume we have permission for everything if authz disabled

    id_resource_map, resources_list = resources_from_objects(drs_objs)

    # gets us a matrix of len(resources_list) rows, 1 column with the permission evaluation result:
    if resources_list:
        authz_results = await authz.async_evaluate(
            request,
            resources_list,
            [permission],
            headers_getter=headers_getter,
            mark_authz_done=mark_authz_done,
        )
    else:  # TODO: when evaluate does this optimization for us, don't bother with this if/else
        authz_results = ()

    # return a tuple of length len(drs_objs) of whether we have the permission for each object
    return tuple(drs_obj.public or authz_results[id_resource_map[drs_obj.id]][0] for drs_obj in drs_objs)


def get_drs_object(session: Session, object_id: str) -> DrsBlob | None:
    return session.scalars(select(DrsBlob).where(DrsBlob.id == object_id)).one_or_none()


async def fetch_and_check_object_permissions(
    session: Session,
    authz: FastApiAuthMiddleware,
    request: Request,
    object_id: str,
    permission: Permission,
    headers_getter: HeadersGetter | None = None,
) -> DrsBlob:
    has_permission_on_everything = await check_everything_permission(authz, request, permission)

    drs_object = get_drs_object(session, object_id)

    # The HTTPException handler marks authorization as determined, so we don't need to do it before raising.

    if not drs_object:
        if authz.enabled and not has_permission_on_everything:  # Don't leak if this object exists
            logger.error("No object found for the requested ID; masking with 403 to prevent ID discovery")
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No object found for this ID")

    # Check permissions -------------------------------------------------
    if has_permission_on_everything:
        # Good to go already!
        authz.mark_authz_done(request)
    else:
        p = await check_objects_permission(
            authz, request, [drs_object], permission, mark_authz_done=True, headers_getter=headers_getter
        )
        if not p[0]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    # -------------------------------------------------------------------

    return drs_object


def bad_request_log(err: str) -> HTTPException:
    logger.error(err)
    return HTTPException(status.HTTP_400_BAD_REQUEST, err)


def range_not_satisfiable_log(description: str, length: int) -> HTTPException:
    logger.error("Requested range not satisfiable: %s; true length: %d", description, length)
    return HTTPException(status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, description)


# Each endpoint is available both at the root and under the GA4GH DRS spec's path prefix.


@drs_router.get("/objects/{object_id}", response_model=DrsBlobResponse)
@drs_router.get("/ga4gh/drs/v1/objects/{object_id}", response_model=DrsBlobResponse)
async def object_info(
    object_id: str,
    request: Request,
    session: SessionDep,
    authz: AuthzMiddlewareDep,
    config: ConfigDep,
    # The requester can ask for additional, non-spec-compliant Bento properties to be included in the response
    with_bento_properties: LenientBool = False,
    # The requester can specify object internal path to be added to the response
    internal_path: LenientBool = False,
):
    drs_object = await fetch_and_check_object_permissions(session, authz, request, object_id, P_QUERY_DATA)
    return build_blob_response(
        config, drs_object, inside_container=internal_path, with_bento_properties=with_bento_properties
    )


@drs_router.delete("/objects/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
@drs_router.delete("/ga4gh/drs/v1/objects/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def object_delete(object_id: str, request: Request, session: SessionDep, authz: AuthzMiddlewareDep):
    drs_object = await fetch_and_check_object_permissions(session, authz, request, object_id, P_DELETE_DATA)

    logger.info("Deleting object %s", drs_object.id)

    cond = DrsBlob.location == drs_object.location
    if (
        session.scalars(select(func.count("*")).select_from(DrsBlob).where(cond)).one() == 1
        and session.scalars(select(DrsBlob).where(cond)).one().id == drs_object.id
    ):
        # If this object is the only one using the file, delete the file too
        # TODO: this can create a race condition and leave files undeleted... should we have a cleanup on start?
        logger.info(
            f"Deleting file at {drs_object.location}, since {drs_object.id} is the only object referring to it."
        )
        backend = get_backend()
        await backend.delete(drs_object.location)

    session.delete(drs_object)
    session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@drs_router.get("/objects/{object_id}/access/{access_id}")
@drs_router.get("/ga4gh/drs/v1/objects/{object_id}/access/{access_id}")
async def object_access(
    object_id: str, access_id: str, request: Request, session: SessionDep, authz: AuthzMiddlewareDep
):
    await fetch_and_check_object_permissions(session, authz, request, object_id, P_QUERY_DATA)

    # We explicitly do not support access_id-based accesses; all of them will be 'not found'
    # since we don't provide access IDs

    # TODO: Eventually generate one-time signed URLs or something?

    raise HTTPException(status.HTTP_404_NOT_FOUND, f"No access ID '{access_id}' exists for object '{object_id}'")


def _build_filter_clauses(
    name: str | None,
    fuzzy_name: str | None,
    search_q: str | None,
    project: str | None,
    datasets: list[str],
    data_types: list[str],
) -> list[ColumnElement]:
    # we can optionally pass query params limiting/filtering the search response to a specific scope
    filter_clauses = []
    if project:
        filter_clauses.append(DrsBlob.project_id == project)
    if datasets:
        filter_clauses.append(or_(*(DrsBlob.dataset_id == d for d in datasets)))
    if data_types:
        filter_clauses.append(or_(*(DrsBlob.data_type == dt for dt in data_types)))

    # different branches for different possible searches - we only use one of them.
    if name:
        filter_clauses.append(DrsBlob.name == name)
    elif fuzzy_name:
        filter_clauses.append(DrsBlob.name.contains(fuzzy_name))
    elif search_q:
        filter_clauses.append(
            or_(
                DrsBlob.id.contains(search_q),
                DrsBlob.name.contains(search_q),
                DrsBlob.checksum.contains(search_q),
                DrsBlob.description.contains(search_q),
            )
        )
    return filter_clauses


@drs_router.get("/search", response_model=list[DrsBlobResponse])
async def object_search(
    request: Request,
    session: SessionDep,
    authz: AuthzMiddlewareDep,
    config: ConfigDep,
    name: str | None = None,
    fuzzy_name: str | None = None,
    q: str | None = None,
    project: str | None = None,
    dataset: Annotated[list[str] | None, Query()] = None,
    data_type: Annotated[list[str] | None, Query()] = None,
    internal_path: LenientBool = False,
    with_bento_properties: LenientBool = False,
):
    # we can optionally pass query params limiting/filtering the search response to a specific scope
    filter_clauses = _build_filter_clauses(
        name=name,
        fuzzy_name=fuzzy_name,
        search_q=q,
        project=project,
        datasets=dataset or [],
        data_types=data_type or [],
    )

    # search requires: (name XOR fuzzy_name XOR q) | project | dataset (1+) | data_type (1+)
    if not filter_clauses:
        raise bad_request_log("Missing GET search terms: (name XOR fuzzy_name XOR q) | project | dataset | data_type")

    objects = list(session.scalars(select(DrsBlob).where(*filter_clauses)).all())

    # TODO: invert the permissions logic - get IDs of projects/datasets where we have query:data access, to avoid this
    #  gross O(n) lookup when searching. Although at least it's now O(n) in terms of number of resources, not number
    #  of objects.
    # TODO: it's also important to pre-check list of resources with query:data access to avoid timing attacks.

    permissions = await check_objects_permission(authz, request, objects, P_QUERY_DATA)
    response = [
        # Only include the blob in the search results if we have permissions to view it.
        build_blob_response(config, obj, internal_path, with_bento_properties=with_bento_properties)
        for obj, p in zip(objects, permissions)
        if p
    ]

    authz.mark_authz_done(request)
    return response


async def _download_object(
    request: Request,
    session: Session,
    authz: FastApiAuthMiddleware,
    object_id: str,
    headers_getter: HeadersGetter | None = None,
) -> StreamingResponse:
    drs_object = await fetch_and_check_object_permissions(
        session, authz, request, object_id, P_DOWNLOAD_DATA, headers_getter
    )
    obj_size = drs_object.size

    mime_type: str = drs_object.mime_type or MIME_OCTET_STREAM
    response_headers = attachment_header(drs_object.name)

    # Adjust headers and streaming args if a range is provided
    range_header = request.headers.get("Range")
    bytes_range = None
    if range_header:
        try:
            range_intervals = parse_range_header(range_header, obj_size)
        except StreamingBadRange as e:
            raise bad_request_log(str(e))
        except StreamingRangeNotSatisfiable as e:
            raise range_not_satisfiable_log(str(e), obj_size)
        bytes_range = range_intervals[0]
        start, end = bytes_range
        response_headers["Content-Length"] = str(end + 1 - start)  # byte range is inclusive, so need to add one
        response_headers["Content-Range"] = f"bytes {start}-{end}/{obj_size}"
    else:
        response_headers["Accept-Ranges"] = "bytes"
        response_headers["Content-Length"] = str(obj_size)

    # Get the streaming generator from the backend (local | S3)
    try:
        obj_generator = await drs_object.get_streaming_generator(bytes_range)
    except StreamingException as e:
        raise bad_request_log(str(e))

    status_code: int = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK
    return StreamingResponse(obj_generator, status_code=status_code, media_type=mime_type, headers=response_headers)


@drs_router.get("/objects/{object_id}/download")
async def object_download(object_id: str, request: Request, session: SessionDep, authz: AuthzMiddlewareDep):
    return await _download_object(request, session, authz, object_id)


@drs_router.post("/objects/{object_id}/download")
async def object_download_post(
    object_id: str,
    request: Request,
    session: SessionDep,
    authz: AuthzMiddlewareDep,
    # A token can be passed in the form body (instead of an Authorization header), e.g., for browser form submissions
    token: Annotated[str | None, Form()] = None,
):
    def headers_getter(_r: Request) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"} if token else {}

    return await _download_object(request, session, authz, object_id, headers_getter)


def _save_upload(upload: UploadFile, path: str) -> None:
    with open(path, "wb") as fh:
        shutil.copyfileobj(upload.file, fh)


@drs_router.post("/ingest", response_model=DrsBlobResponse, status_code=status.HTTP_201_CREATED)
async def object_ingest(
    request: Request,
    session: SessionDep,
    authz: AuthzMiddlewareDep,
    config: ConfigDep,
    # All form fields are optional so that authorization is evaluated before any 4xx caused by the request body, e.g.,
    # an unauthorized request with an empty body should get a 403.
    deduplicate: Annotated[LenientBool, Form()] = True,  # Change for v0.9: default to True
    path: Annotated[str | None, Form()] = None,
    project_id: Annotated[str | None, Form()] = None,
    dataset_id: Annotated[str | None, Form()] = None,
    data_type: Annotated[str | None, Form()] = None,
    public: Annotated[str, Form()] = "false",
    mime_type: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
):
    obj_path: str | None = path
    # replace blank strings with None
    project_id = project_id or None
    dataset_id = dataset_id or None
    data_type = data_type or None
    mime_type = mime_type or None
    is_public: bool = public.strip().lower() == "true"

    logger.info(
        "Received ingest request metadata: deduplicate=%s path=%s project_id=%s dataset_id=%s data_type=%s "
        "public=%s mime_type=%s",
        deduplicate,
        path,
        project_id,
        dataset_id,
        data_type,
        public,
        mime_type,
    )

    # This authz call determines everything, so we can mark authz as done when the call completes:
    has_permission: bool = (
        await authz.async_evaluate_one(
            request,
            build_resource(project_id, dataset_id, data_type),
            P_INGEST_DATA,
            mark_authz_done=True,
        )
        if authz.enabled
        else True
    )

    if not has_permission:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    if (obj_path is not None and file is not None) or (obj_path is None and file is None):
        raise bad_request_log("Must specify exactly one of path or file contents")

    drs_object: DrsBlob | None = None  # either the new object, or the object to fully reuse
    object_to_copy: DrsBlob | None = None

    tfh, t_obj_path = tempfile.mkstemp(dir=config.drs_ingest_tmp_dir)
    try:
        filename: str | None = None  # no override, use path filename if path is specified instead of a file upload
        if file is not None:
            logger.debug("ingest - received file object: %s", file)
            logger.debug("ingest - writing to temporary path: %s", t_obj_path)
            await asyncio.to_thread(_save_upload, file, t_obj_path)
            obj_path = t_obj_path
            filename = file.filename  # still may be none, in which case the temporary filename will be used

        if deduplicate:
            # Get checksum of original file, and query database for objects that match

            try:
                checksum = await asyncio.to_thread(drs_file_checksum, obj_path)
            except FileNotFoundError:
                raise bad_request_log(f"File not found at path {obj_path}")

            # Currently, we require exact permissions compatibility for deduplication of IDs.
            # It might be possible to relax this a bit, but we can't fully relax this for two reasons:
            #  - we would need to keep track of sets of permissions for each DRS object
            #  - certain attacks may be performable by creating a second project/dataset in a semi-public instance
            #    and seeing which files are DRS ID duplicates.
            # However, we can actually deduplicate the files on the filesystem as these are more opaque.

            candidate_drs_object: DrsBlob | None = session.scalars(
                select(DrsBlob).where(DrsBlob.checksum == checksum)
            ).one_or_none()

            if candidate_drs_object is not None:
                c_project_id = candidate_drs_object.project_id
                c_dataset_id = candidate_drs_object.dataset_id
                c_data_type = candidate_drs_object.data_type
                c_public = candidate_drs_object.public

                if (
                    c_project_id == project_id
                    and c_dataset_id == dataset_id
                    and c_data_type == data_type
                    and c_public == is_public
                ):
                    logger.info(
                        f"Found duplicate DRS object via checksum (will fully deduplicate): {candidate_drs_object}"
                    )
                    drs_object = candidate_drs_object
                else:
                    logger.info(
                        f"Found duplicate DRS object via checksum (will deduplicate JUST bytes; req resource: "
                        f"({project_id}, {dataset_id}, {data_type}, {is_public}) vs existing resource: "
                        f"({c_project_id}, {c_dataset_id}, {c_data_type}, {c_public})): "
                        f"{candidate_drs_object}"
                    )
                    object_to_copy = candidate_drs_object

        if not drs_object:
            try:
                drs_object = await DrsBlob.create(
                    **({"object_to_copy": object_to_copy} if object_to_copy else {"location": obj_path}),
                    filename=filename,
                    mime_type=mime_type,
                    project_id=project_id,
                    dataset_id=dataset_id,
                    data_type=data_type,
                    public=is_public,
                )
                session.add(drs_object)
                session.commit()
                logger.info("added DRS object: %s", drs_object)
            except ValueError as e:
                raise bad_request_log(str(e))
            except Exception as e:  # noqa: BLE001  # TODO: More specific handling
                logger.exception("encountered exception during ingest", exc_info=e)
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Error while creating the object")

        return build_blob_response(config, drs_object, with_bento_properties=True)

    finally:
        os.close(tfh)
        os.remove(t_obj_path)
