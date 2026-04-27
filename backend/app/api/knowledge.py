from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.state import get_chat_services
from ..schemas import (
    KnowledgeBatchDeleteIn,
    KnowledgeBatchDeleteResult,
    KnowledgeBatchMoveIn,
    KnowledgeBatchMoveResult,
    KnowledgeBatchUploadResult,
    KnowledgeDocumentOut,
    KnowledgeFolderCreate,
    KnowledgeFolderDeleteIn,
    KnowledgeFolderDeleteResult,
    KnowledgeReindexResult,
    KnowledgeStatusOut,
)
from ..storage.database import get_db
from ..storage.models import User

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_knowledge_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return services.knowledge_service.list_documents(db=db, user_id=current_user.id)


@router.get("/folders", response_model=list[str])
def list_knowledge_folders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return services.knowledge_service.list_folders(db=db, user_id=current_user.id)


@router.post("/folders", response_model=str, status_code=status.HTTP_201_CREATED)
def create_knowledge_folder(
    payload: KnowledgeFolderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    try:
        return services.knowledge_service.create_folder(
            db=db,
            user_id=current_user.id,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/folders", response_model=KnowledgeFolderDeleteResult)
def delete_knowledge_folder(
    payload: KnowledgeFolderDeleteIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    try:
        result = services.knowledge_service.delete_folder(
            db=db,
            user_id=current_user.id,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Knowledge folder not found")
    return KnowledgeFolderDeleteResult(**result)


@router.get("/status", response_model=KnowledgeStatusOut)
def get_knowledge_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return KnowledgeStatusOut(**services.knowledge_service.status(db=db, user_id=current_user.id))


@router.post("/documents", response_model=KnowledgeDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form(""),
    relative_path: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    try:
        return await services.knowledge_service.create_document(
            db=db,
            user_id=current_user.id,
            upload=file,
            folder=folder,
            relative_path=relative_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/batch", response_model=KnowledgeBatchUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_documents_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    folder: str = Form(""),
    relative_paths: Optional[list[str]] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    try:
        documents = await services.knowledge_service.create_documents(
            db=db,
            user_id=current_user.id,
            uploads=files,
            folder=folder,
            relative_paths=relative_paths or [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeBatchUploadResult(
        created_count=len(documents),
        documents=documents,
    )


@router.post("/documents/{document_id}/reindex", response_model=KnowledgeDocumentOut)
async def reindex_knowledge_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    document = await services.knowledge_service.reindex_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    return document


@router.post("/reindex", response_model=KnowledgeReindexResult)
async def reindex_pending_knowledge_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    result = await services.knowledge_service.reindex_pending_documents(
        db=db,
        user_id=current_user.id,
    )
    return KnowledgeReindexResult(**result)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    relative_path = services.knowledge_service.delete_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    if relative_path is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    services.knowledge_service.remove_file(relative_path)


@router.post("/documents/delete", response_model=KnowledgeBatchDeleteResult)
def delete_knowledge_documents_batch(
    payload: KnowledgeBatchDeleteIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    deleted_ids, deleted_paths = services.knowledge_service.delete_documents(
        db=db,
        user_id=current_user.id,
        document_ids=payload.document_ids,
    )
    services.knowledge_service.remove_files(deleted_paths)
    return KnowledgeBatchDeleteResult(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.patch("/documents/folder", response_model=KnowledgeBatchMoveResult)
def move_knowledge_documents_folder(
    payload: KnowledgeBatchMoveIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    try:
        documents = services.knowledge_service.move_documents(
            db=db,
            user_id=current_user.id,
            document_ids=payload.document_ids,
            folder=payload.folder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeBatchMoveResult(
        moved_count=len(documents),
        documents=documents,
    )
