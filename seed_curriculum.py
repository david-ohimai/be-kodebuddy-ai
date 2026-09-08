from datetime import date, datetime, timezone
from sqlmodel import Session, select

from app.core.database import engine
from app.features.auth.model import User, UserRole
from app.features.cohorts.models.model import Cohort
from app.features.courses.model import Course
from app.features.modules.model import Module
from app.features.lessons.model import Lesson
from app.features.resources.model import Resource


def seed_curriculum():
    with Session(engine) as session:
        # 1. Fetch the Admin User (created by seed_admin.py)
        admin = session.exec(
            select(User).where(User.role == UserRole.ADMIN)
        ).first()
        if not admin:
            print("Error: Please run seed_admin.py first to create the admin user.")
            return

        admin_id = admin.id

        # 2. Seed Cohort
        cohort = session.exec(
            select(Cohort).where(Cohort.name == "KodeCamp Cohort 1")
        ).first()
        if not cohort:
            cohort = Cohort(
                name="KodeCamp Cohort 1",
                description="The first cohort of KodeCamp",
                start_date=date(2026, 8, 1),
                end_date=date(2026, 12, 31),
                created_by=admin_id,
            )
            session.add(cohort)
            session.commit()
            session.refresh(cohort)
            print(f"Cohort created: {cohort.name} (ID: {cohort.id})")
        else:
            print(f"Cohort already exists (ID: {cohort.id})")

        # 3. Seed Course
        course = session.exec(
            select(Course).where(Course.title == "Python Programming 101")
        ).first()
        if not course:
            course = Course(
                id=1,  # Set ID explicitly to match FAQs seed database if needed, or let database handle it
                title="Python Programming 101",
                description="Introductory course to python development.",
                cohort_id=cohort.id,
                created_by=admin_id,
                is_active=True,
            )
            session.add(course)
            session.commit()
            session.refresh(course)
            print(f"Course created: {course.title} (ID: {course.id})")
        else:
            print(f"Course already exists (ID: {course.id})")

        # 4. Seed Module
        module = session.exec(
            select(Module).where(Module.title == "Variables & Control Flow")
        ).first()
        if not module:
            module = Module(
                course_id=course.id,
                title="Variables & Control Flow",
                description="Learn the basics of python variables, expressions, and loops.",
                order=1,
                created_by=admin_id,
                is_active=True,
            )
            session.add(module)
            session.commit()
            session.refresh(module)
            print(f"Module created: {module.title} (ID: {module.id})")
        else:
            print(f"Module already exists (ID: {module.id})")

        # 5. Seed Lesson
        lesson = session.exec(
            select(Lesson).where(Lesson.title == "Introduction to Loops")
        ).first()
        if not lesson:
            lesson = Lesson(
                module_id=module.id,
                title="Introduction to Loops",
                content_body="Loops are essential in programming for executing a block of code multiple times. In Python, we have 'for' loops to iterate over sequences and 'while' loops to execute as long as a condition is true.",
                order=1,
                created_by=admin_id,
                is_active=True,
            )
            session.add(lesson)
            session.commit()
            session.refresh(lesson)
            print(f"Lesson created: {lesson.title} (ID: {lesson.id})")
        else:
            print(f"Lesson already exists (ID: {lesson.id})")

        # 6. Seed Resource
        resource = session.exec(
            select(Resource).where(Resource.title == "Python Control Flow Cheat Sheet")
        ).first()
        if not resource:
            resource = Resource(
                module_id=module.id,
                title="Python Control Flow Cheat Sheet",
                description="A quick cheat sheet summarizing python if statements and loops.",
                type="link",
                url="https://docs.python.org/3/tutorial/controlflow.html",
                created_by=admin_id,
                is_active=True,
            )
            session.add(resource)
            session.commit()
            session.refresh(resource)
            print(f"Resource created: {resource.title} (ID: {resource.id})")
        else:
            print(f"Resource already exists (ID: {resource.id})")

        print("Curriculum seeded successfully!")


if __name__ == "__main__":
    seed_curriculum()