from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.goal import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    GoalContribute,
)
from backend.app.api.dependencies import get_current_user
from backend.app.services.goal_service import GoalService

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("/", response_model=List[GoalResponse])
def get_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    return service.list_goals(current_user.id)


@router.post(
    "/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED
)
def create_goal(
    goal_in: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    return service.create_goal(current_user.id, goal_in)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    return service.get_goal(current_user.id, goal_id)


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: UUID,
    goal_in: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    return service.update_goal(current_user.id, goal_id, goal_in)


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
def contribute_to_goal(
    goal_id: UUID,
    contribution: GoalContribute,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    return service.contribute_to_goal(current_user.id, goal_id, contribution)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    service.delete_goal(current_user.id, goal_id)
    return None
