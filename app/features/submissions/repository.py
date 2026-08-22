from sqlmodel import Session, select
from .model import Submission

class SubmissionRepository:
    def __init__(self, session: Session):
        self.session = session


    def get_submission_by_id(self, submission_id: int) -> Submission | None:
        return self.session.get(Submission, submission_id)
    

    def get_submissions_by_assignment_learner(self, assignment_id: int, learner_id: int) -> Submission | None:
        statement = select(Submission).where(
            Submission.assignment_id == assignment_id, 
            Submission.learner_id == learner_id
            )
        return self.session.exec(statement).first()
    

    def get_by_learner_id(self, learner_id: int) -> list[Submission]:
        statement = select(Submission).where(Submission.learner_id == learner_id)
        return list(self.session.exec(statement).all())
    

    def get_by_assignment_id(self, assignment_id: int) -> list[Submission]:
        statement = select(Submission).where(
            Submission.assignment_id == assignment_id
            )
        return list(self.session.exec(statement).all())
    

    def create_submission(self, submission_data: dict)-> Submission:
        submission = Submission(**submission_data)

        self.session.add(submission)
        self.session.commit()
        self.session.refresh(submission)
        
        return submission
    

    def update_submission(self, submission_id: int, update_data: dict)-> Submission | None:
        submission = self.get_submission_by_id(submission_id)

        if  submission is None:
            return None

        for key, value in update_data.items():
                setattr(submission, key, value)

        self.session.add(submission)
        self.session.commit()
        self.session.refresh(submission)

        return submission
    

    def delete_submission(self, submission_id: int)-> bool:
        submission = self.get_submission_by_id(submission_id)

        if  submission is None:
            return False
        
        self.session.delete(submission)
        self.session.commit()
        
        return True
        
       