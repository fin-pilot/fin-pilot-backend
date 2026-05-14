from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import Goal


class GoalRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[Goal]:
        return self._db.query(Goal).filter(Goal.user_id == user_id).all()

    def get_by_id_for_user(self, goal_id: UUID, user_id: UUID) -> Goal | None:
        return (
            self._db.query(Goal)
            .filter(Goal.id == goal_id, Goal.user_id == user_id)
            .first()
        )

    def add(self, goal: Goal) -> Goal:
        self._db.add(goal)
        return goal

    def delete(self, goal: Goal) -> None:
        self._db.delete(goal)
