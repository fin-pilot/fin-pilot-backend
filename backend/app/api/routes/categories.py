from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
import uuid

from app.db.database import get_db
from app.db.models import Category, User
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Category)
        .filter(
            or_(Category.user_id == current_user.id, Category.user_id is None)
        )
        .all()
    )


@router.post(
    "/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_category = Category(**category_in.model_dump(), user_id=current_user.id)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category


@router.put("/{id}", response_model=CategoryResponse)
def update_category(
    category_id: uuid.UUID,
    category_in: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == current_user.id)
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=404, detail="Category not found or access denied"
        )

    update_data = category_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)

    db.commit()
    db.refresh(category)
    return category


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == current_user.id)
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=404, detail="Category not found or access denied"
        )

    db.delete(category)
    db.commit()
    return None
