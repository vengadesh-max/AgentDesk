import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Conversation, Message, Project, User
from app.schemas import ChatRequest, ChatResponse, ConversationResponse, MessageResponse
from app.services.llm import generate_chat_response

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _get_owned_project(project_id: str, user: User, db: Session) -> Project:
    project = (
        db.query(Project)
        .options(joinedload(Project.prompts), joinedload(Project.files))
        .filter(Project.id == project_id, Project.owner_id == user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    conversations = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.project_id == project_id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    project_id: str,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_project(project_id, current_user, db)
    conversation = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post("", response_model=ChatResponse)
async def send_message(
    project_id: str,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_owned_project(project_id, current_user, db)

    if payload.conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == payload.conversation_id, Conversation.project_id == project_id)
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    else:
        title = payload.message[:80] + ("..." if len(payload.message) > 80 else "")
        conversation = Conversation(project_id=project_id, title=title)
        db.add(conversation)
        db.flush()

    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message)
    db.add(user_message)
    db.flush()

    try:
        assistant_content = await generate_chat_response(
            db, project, conversation, payload.message, current_user.id
        )
    except Exception as e:
        logger.exception("LLM chat failed for project %s", project_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=assistant_content)
    db.add(assistant_message)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )
