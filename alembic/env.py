from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from sqlmodel import SQLModel

from app.core.config import DATABASE_URL

from app.features.auth.model import User

from app.features.cohorts.models.model import Cohort
from app.features.cohorts.models.cohort_learners import (
    CohortLearner,
    CohortTrainer,
)

from app.features.courses.model import Course, CourseTrainer

from app.features.modules.model import Module
from app.features.lessons.model import Lesson
from app.features.progress.model import UserProgress

from app.features.assignments.model import Assignment
from app.features.resources.model import Resource, ResourceType
from app.features.submissions.model import Submission

from app.agent.model import ContentEmbedding, Escalation, ConversationHistory, QueryLog



# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL,
)


# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Add your model's MetaData object here
# for 'autogenerate' support.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()