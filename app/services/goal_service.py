from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import Goal
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalContribute, GoalCreate, GoalUpdate


class GoalService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = GoalRepository(db)

    def list_goals(self, user_id: UUID) -> list[Goal]:
        return self._repo.list_by_user(user_id)

    def get_goal(self, user_id: UUID, goal_id: UUID) -> Goal:
        goal = self._repo.get_by_id_for_user(goal_id, user_id)
        if not goal:
            raise NotFoundError("Ціль не знайдена")
        return goal

    def create_goal(self, user_id: UUID, goal_in: GoalCreate) -> Goal:
        goal = Goal(
            user_id=user_id,
            name=goal_in.name,
            target_amount=goal_in.target_amount,
            current_amount=goal_in.current_amount or 0.0,
            deadline=goal_in.deadline,
        )
        
        try:
            self._repo.add(goal)
            self._db.commit()
            self._db.refresh(goal)
            return goal
        except Exception:
            self._db.rollback()
            raise

    def update_goal(
        self,
        user_id: UUID,
        goal_id: UUID,
        goal_in: GoalUpdate,
    ) -> Goal:
        goal = self._repo.get_by_id_for_user(goal_id, user_id)
        if not goal:
            raise NotFoundError("Ціль не знайдена")

        update_data = goal_in.model_dump(exclude_unset=True)
        if update_data:
            try:
                for key, value in update_data.items():
                    setattr(goal, key, value)
                
                self._db.commit()
                self._db.refresh(goal)
            except Exception:
                self._db.rollback()
                raise

        return goal

    def contribute_to_goal(
        self,
        user_id: UUID,
        goal_id: UUID,
        contribution: GoalContribute,
    ) -> Goal:
        goal = self._repo.get_by_id_for_user(goal_id, user_id)
        if not goal:
            raise NotFoundError("Ціль не знайдена")

        try:
            goal.current_amount += contribution.amount
            self._db.commit()
            self._db.refresh(goal)
            return goal
        except Exception:
            self._db.rollback()
            raise

    def delete_goal(self, user_id: UUID, goal_id: UUID) -> None:
        goal = self._repo.get_by_id_for_user(goal_id, user_id)
        if not goal:
            raise NotFoundError("Ціль не знайдена")
            
        try:
            self._repo.delete(goal)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise