from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Project, ProjectFile, User
from app.schemas import FileResponse
from app.services.llm import delete_from_llm, save_upload_file, upload_to_llm

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])
settings = get_settings()


def _get_owned_project(project_id: str, user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[FileResponse])
def list_files(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    return db.query(ProjectFile).filter(ProjectFile.project_id == project_id).order_by(ProjectFile.created_at.desc()).all()


@router.post("", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )

    original_name = file.filename or "upload"
    filename, file_path = save_upload_file(project_id, original_name, content, file.content_type)

    openai_file_id = await upload_to_llm(file_path, original_name)

    project_file = ProjectFile(
        project_id=project_id,
        filename=filename,
        original_name=original_name,
        content_type=file.content_type,
        size_bytes=len(content),
        openai_file_id=openai_file_id,
    )
    db.add(project_file)
    db.commit()
    db.refresh(project_file)
    return project_file


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    project_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    project_file = db.query(ProjectFile).filter(ProjectFile.id == file_id, ProjectFile.project_id == project_id).first()
    if not project_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if project_file.openai_file_id:
        await delete_from_llm(project_file.openai_file_id)

    file_path = Path(settings.upload_dir) / project_id / project_file.filename
    if file_path.exists():
        file_path.unlink()

    db.delete(project_file)
    db.commit()
