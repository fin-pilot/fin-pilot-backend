from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from backend.app.db.database import get_db
from backend.app.db.models import Goal, User
from backend.app.schemas.goal import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    GoalContribute,
)
from backend.app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("/", response_model=List[GoalResponse])
def get_goals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Goal).filter(Goal.user_id == current_user.id).all()


@router.post(
    "/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED
)
def create_goal(
    goal_in: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_goal = Goal(
        user_id=current_user.id,
        name=goal_in.name,
        target_amount=goal_in.target_amount,
        current_amount=goal_in.current_amount,
        deadline=goal_in.deadline,
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    return new_goal


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == current_user.id)
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Ціль не знайдена")
    return goal


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: UUID,
    goal_in: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == current_user.id)
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Ціль не знайдена")

    update_data = goal_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(goal, key, value)

    db.commit()
    db.refresh(goal)
    return goal


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
def contribute_to_goal(
    goal_id: UUID,
    contribution: GoalContribute,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == current_user.id)
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Ціль не знайдена")

    goal.current_amount += contribution.amount

    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = (
        db.query(Goal)
        .filter(Goal.id == goal_id, Goal.user_id == current_user.id)
        .first()
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Ціль не знайдена")

    db.delete(goal)
    db.commit()
    return None
