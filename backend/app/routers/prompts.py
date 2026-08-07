from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Project, Prompt, User
from app.schemas import PromptCreate, PromptResponse, PromptUpdate

router = APIRouter(prefix="/projects/{project_id}/prompts", tags=["prompts"])


def _get_owned_project(project_id: str, user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[PromptResponse])
def list_prompts(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    return db.query(Prompt).filter(Prompt.project_id == project_id).order_by(Prompt.updated_at.desc()).all()


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(
    project_id: str,
    payload: PromptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    prompt = Prompt(project_id=project_id, name=payload.name, content=payload.content)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("/{prompt_id}", response_model=PromptResponse)
def get_prompt(
    project_id: str,
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project_id).first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    return prompt


@router.patch("/{prompt_id}", response_model=PromptResponse)
def update_prompt(
    project_id: str,
    prompt_id: str,
    payload: PromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project_id).first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    if payload.name is not None:
        prompt.name = payload.name
    if payload.content is not None:
        prompt.content = payload.content
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    project_id: str,
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project_id).first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    db.delete(prompt)
    db.commit()
