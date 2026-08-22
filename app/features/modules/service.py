from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.features.auth.model import User, UserRole
from app.features.courses.model import Course, CourseTrainer, CourseLearner

from .model import Module
from .repository import ModuleRepository
from .schema import ModuleCreate, ModuleUpdate, ReorderModulesRequest

# ---------- AUTHORIZATION HELPERS ----------
def verify_trainer_course_access( 
    session: Session,
    current_user: User,
    course_id: int,
) -> None:

    # Admin can manage every course/module
    if current_user.role.value == "admin":
        return

    if current_user.role.value != "trainer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this course",
        )

    # Check whether this trainer is assigned to the course. 
    course = session.get(Course, course_id)

    if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )
    
    statement = select(CourseTrainer).where(
        CourseTrainer.course_id == course_id,
        CourseTrainer.trainer_id == current_user.id,
    )
    
    assignment = session.exec(statement).first()

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this course",
        )


def verify_trainer_module_access(
    session: Session,
    current_user: User,
    module: Module,
) -> None:

    verify_trainer_course_access(
        session=session,
        current_user=current_user,
        course_id=module.course_id,
    )


def verify_learner_course_access(
    session: Session,
    current_user: User,
    course_id: int,
) -> None:

    if current_user.role.value != "learner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this course",
        )

    course = session.get(Course, course_id)

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    # Check whether the learner is assigned to the course.
    statement = select(CourseLearner).where(
        CourseLearner.course_id == course_id,
        CourseLearner.learner_id == current_user.id,
    )

    assignment = session.exec(statement).first()

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this course",
        )

    
def verify_mentor_course_access(
    session: Session,
    current_user: User,
    course_id: int,
) -> None:
 
    if current_user.role != UserRole.MENTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mentor access required",
        )

    course = session.get(Course, course_id)

    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not authorized to access this course",
    )


class ModuleService:
    def __init__(self, repository: ModuleRepository, session: Session):
        self.repository = repository
        self.session = session


    def create_module(self, data: ModuleCreate, current_user: User) -> Module:

        # Verify course exists
        course = self.session.get(Course, data.course_id)

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )

        # Verify trainer/admin access
        verify_trainer_course_access(
            session=self.session,
            current_user=current_user,
            course_id=data.course_id,
        )

        module = Module(
            course_id=data.course_id,
            title=data.title,
            description=data.description,
            order=data.order,
            created_by=current_user.id,
        )
        return self.repository.create(module)


    def get_module(
        self,
        module_id: int,
        current_user: User,
    ) -> Module:

        module = self.repository.get_active_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        # Admin can view everything.
        if current_user.role == UserRole.ADMIN:
            return module
        
        # Trainer can view modules in assigned courses.
        if current_user.role == UserRole.TRAINER:
            verify_trainer_module_access(
                session=self.session,
                current_user=current_user,
                module=module,
            )
            return module

        # Learner can view modules in assigned courses.
        if current_user.role == UserRole.LEARNER:
            verify_learner_course_access(
                session=self.session,
                current_user=current_user,
                course_id=module.course_id,
            )
            return module

         # Mentor can view only where explicitly authorized.
        if current_user.role == UserRole.MENTOR:
            verify_mentor_course_access(
                session=self.session,
                current_user=current_user,
                course_id=module.course_id,
            )
            return module

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this module",
        )


    def get_modules_for_course(
        self,
        course_id: int,
        current_user: User,
    ) -> list[Module]:

        course = self.session.get(Course, course_id)

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )

        # Admin
        if current_user.role == UserRole.ADMIN:
            return self.repository.get_by_course_id(course_id)

        # Trainer
        if current_user.role == UserRole.TRAINER:
            verify_trainer_course_access(
                session=self.session,
                current_user=current_user,
                course_id=course_id,
            )

        # Learner
        elif current_user.role == UserRole.LEARNER:
            verify_learner_course_access(
                session=self.session,
                current_user=current_user,
                course_id=course_id,
            )

        # Mentor.
        elif current_user.role == UserRole.MENTOR:
            verify_mentor_course_access(
                session=self.session,
                current_user=current_user,
                course_id=course_id,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access course modules",
            )

        return self.repository.get_by_course_id(course_id)


    def update_module(self, module_id: int, data: ModuleUpdate, current_user: User) -> Module:
        module = self.repository.get_active_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        verify_trainer_module_access(
            session=self.session,
            current_user=current_user,
            module=module,
        )

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(module, field, value)

        module.updated_at = datetime.now(timezone.utc)

        return self.repository.update(module)


    def delete_module(self,  module_id: int, current_user: User) -> Module:
        module = self.repository.get_active_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        verify_trainer_module_access(
            session=self.session,
            current_user=current_user,
            module=module,
        )

        return self.repository.deactivate(module)


    def reorder_modules(self, data: ReorderModulesRequest, current_user: User) -> list[Module]:

        # Verify trainer/admin access to the course
        verify_trainer_course_access(
            session=self.session,
            current_user=current_user,
            course_id=data.course_id
        )

        requested_ids = [item.id for item in data.modules]

        if len(requested_ids) != len(set(requested_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate module IDs are not allowed"
            )

        modules = self.repository.get_by_ids(requested_ids)

        found_ids = {module.id for module in modules}
        missing_ids = set(requested_ids) - found_ids

        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module(s) not found: {sorted(missing_ids)}",
            )

        # Make sure every module belongs to this course
        invalid_modules = [
            module.id
            for module in modules
            if module.course_id != data.course_id
        ]

        if invalid_modules:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more modules do not belong to this course",
            )

        order_map = {item.id: item.order for item in data.modules}

        for module in modules:
            module.order = order_map[module.id]
            module.updated_at = datetime.now(timezone.utc)

        return self.repository.bulk_update_order(modules)