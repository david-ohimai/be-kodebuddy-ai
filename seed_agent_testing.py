"""
Seed data needed to actually exercise the agent end-to-end, on top of
seed_admin.py + seed_curriculum.py:
  - a learner user (get_current_learner requires role == LEARNER)
  - that learner enrolled in course_learners (is_enrolled's RBAC check)
  - a trainer user + course_trainers link (so escalations have somewhere
    to land -- _resolve_trainer_id in service.py)
  - one Assignment row under the seeded module (so /agent/chat with
    assignment_id set actually resolves via get_assignment_brief)

Run after seed_admin.py and seed_curriculum.py, in that order:
    python seed_admin.py
    python seed_curriculum.py
    python seed_agent_testing.py
"""

import os
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.database import engine
from app.core.security import hash_password
from app.features.auth.model import User, UserRole
from app.features.courses.model import Course, CourseLearner, CourseTrainer
from app.features.modules.model import Module
from app.features.assignments.model import Assignment

LEARNER_EMAIL = "learner@kodebuddyai.com"
LEARNER_PASSWORD = os.getenv("SEED_LEARNER_PASSWORD", "learner-test-pass-123")

TRAINER_EMAIL = "trainer@kodebuddyai.com"
TRAINER_PASSWORD = os.getenv("SEED_TRAINER_PASSWORD", "trainer-test-pass-123")


def seed_agent_testing():
    with Session(engine) as session:
        # 1. Learner user
        learner = session.exec(
            select(User).where(User.email == LEARNER_EMAIL)
        ).first()
        if not learner:
            learner = User(
                email=LEARNER_EMAIL,
                hashed_password=hash_password(LEARNER_PASSWORD),
                role=UserRole.LEARNER,
                full_name="Test Learner",
                is_active=True,
            )
            session.add(learner)
            session.commit()
            session.refresh(learner)
            print(f"Learner created: {learner.email} (ID: {learner.id})")
        else:
            print(f"Learner already exists (ID: {learner.id})")

        # 2. Trainer user
        trainer = session.exec(
            select(User).where(User.email == TRAINER_EMAIL)
        ).first()
        if not trainer:
            trainer = User(
                email=TRAINER_EMAIL,
                hashed_password=hash_password(TRAINER_PASSWORD),
                role=UserRole.TRAINER,
                full_name="Test Trainer",
                is_active=True,
            )
            session.add(trainer)
            session.commit()
            session.refresh(trainer)
            print(f"Trainer created: {trainer.email} (ID: {trainer.id})")
        else:
            print(f"Trainer already exists (ID: {trainer.id})")

        # 3. Course + module seeded by seed_curriculum.py
        course = session.exec(
            select(Course).where(Course.title == "Python Programming 101")
        ).first()
        if not course:
            print("Error: run seed_curriculum.py first to create the course.")
            return

        module = session.exec(
            select(Module).where(Module.title == "Variables & Control Flow")
        ).first()
        if not module:
            print("Error: run seed_curriculum.py first to create the module.")
            return

        # 4. Enroll the learner (is_enrolled's RBAC check reads this table)
        enrollment = session.exec(
            select(CourseLearner).where(
                CourseLearner.course_id == course.id,
                CourseLearner.learner_id == learner.id,
            )
        ).first()
        if not enrollment:
            enrollment = CourseLearner(course_id=course.id, learner_id=learner.id)
            session.add(enrollment)
            session.commit()
            print(f"Enrolled learner {learner.id} in course {course.id}")
        else:
            print(f"Learner already enrolled in course {course.id}")

        # 5. Assign the trainer to the course (escalation routing)
        assignment_link = session.exec(
            select(CourseTrainer).where(
                CourseTrainer.course_id == course.id,
                CourseTrainer.trainer_id == trainer.id,
            )
        ).first()
        if not assignment_link:
            assignment_link = CourseTrainer(
                course_id=course.id, trainer_id=trainer.id
            )
            session.add(assignment_link)
            session.commit()
            print(f"Assigned trainer {trainer.id} to course {course.id}")
        else:
            print(f"Trainer already assigned to course {course.id}")

        # 6. An Assignment row, so assignment_id in /agent/chat resolves
        assignment = session.exec(
            select(Assignment).where(
                Assignment.title == "Build a FastAPI CRUD router"
            )
        ).first()
        if not assignment:
            assignment = Assignment(
                module_id=module.id,
                title="Build a FastAPI CRUD router",
                description=(
                    "Implement create, read, update and delete endpoints "
                    "for a single resource using FastAPI and SQLModel."
                ),
                due_date=datetime(2026, 9, 15, 23, 59, tzinfo=timezone.utc),
                maximum_score=100.0,
                created_by=course.created_by,
            )
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            print(f"Assignment created: {assignment.title} (ID: {assignment.id})")
        else:
            print(f"Assignment already exists (ID: {assignment.id})")

        print("\nAgent testing seed complete:")
        print(f"  course_id     = {course.id}")
        print(f"  module_id     = {module.id}")
        print(f"  assignment_id = {assignment.id}")
        print(f"  learner login = {LEARNER_EMAIL} / {LEARNER_PASSWORD}")


if __name__ == "__main__":
    seed_agent_testing()