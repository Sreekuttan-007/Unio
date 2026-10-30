from fastapi import Depends, Response

from app.core.access import GuardedRouter, authenticated
from app.core.authuser import AuthUser
from app.services import Services, get_services

router = GuardedRouter(prefix="/api/v1", tags=["files"])


@router.get("/files/{file_id}")
async def download_file(file_id: str, user: AuthUser = Depends(authenticated), services: Services = Depends(get_services)) -> Response:
    """Row-level access is decided by the file store: an owner, or someone who may read the thing it belongs to."""
    meta, data = await services.files.read(user, file_id)
    return Response(content=data, media_type=meta["mime"], headers={"Content-Disposition": f'inline; filename="{meta["name"]}"', "Cache-Control": "private, max-age=300"})
