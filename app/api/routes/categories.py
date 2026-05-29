from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.db.database import get_db
from app.db.models import User
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.api.dependencies import get_current_user
from app.services.category_service import CategoryService

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CategoryService(db)
    return service.list_categories(current_user.id)


@router.post(
    "/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CategoryService(db)
    return service.create_category(current_user.id, category_in)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CategoryService(db)
    return service.update_category(current_user.id, category_id, category_in)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CategoryService(db)
    service.delete_category(current_user.id, category_id)
    return None
