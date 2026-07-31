from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    # 即使开发环境打开 SQL 日志，也不输出 API Key、密码等绑定参数。
    hide_parameters=True,
    pool_pre_ping=True,
)
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    # 创建表前先导入模型，确保 SQLAlchemy 已收集全部表结构。
    from app.models import (  # noqa: F401
        agent_run,
        llm_provider,
        match_result,
        parse_template,
        parse_result,
        qualification,
        task,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        for statement in _LEGACY_SCHEMA_MIGRATIONS:
            await connection.execute(text(statement))


async def close_database() -> None:
    await engine.dispose()


# 旧开发库没有 alembic，用幂等 SQL 补齐新增列/外键/索引；
# 新库由 create_all 直接建好，这些语句会被跳过。
# asyncpg 不允许一次 execute 包含多条语句，因此逐条执行。
_LEGACY_SCHEMA_MIGRATIONS: tuple[str, ...] = (
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tasks'
              AND column_name = 'parse_template_id'
        ) THEN
            ALTER TABLE tasks ADD COLUMN parse_template_id UUID;
            ALTER TABLE tasks
                ADD CONSTRAINT fk_tasks_parse_template_id_task
                FOREIGN KEY (parse_template_id)
                REFERENCES parse_templates (id)
                ON DELETE SET NULL;
            CREATE INDEX IF NOT EXISTS ix_tasks_parse_template_id
                ON tasks (parse_template_id);
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'task_parse_results'
              AND column_name = 'template_id'
        ) THEN
            ALTER TABLE task_parse_results ADD COLUMN template_id UUID;
            ALTER TABLE task_parse_results
                ADD CONSTRAINT fk_task_parse_results_template_id_task
                FOREIGN KEY (template_id)
                REFERENCES parse_templates (id)
                ON DELETE SET NULL;
            CREATE INDEX IF NOT EXISTS ix_task_parse_results_template_id
                ON task_parse_results (template_id);
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'task_parse_results'
              AND column_name = 'template_version'
        ) THEN
            ALTER TABLE task_parse_results
                ADD COLUMN template_version VARCHAR(32);
            CREATE INDEX IF NOT EXISTS
                ix_task_parse_results_template_version
                ON task_parse_results (template_version);
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'task_parse_results'
              AND column_name = 'is_rejected'
        ) THEN
            ALTER TABLE task_parse_results
                ADD COLUMN is_rejected BOOLEAN NOT NULL DEFAULT FALSE;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'task_parse_results'
              AND column_name = 'reject_reason'
        ) THEN
            ALTER TABLE task_parse_results ADD COLUMN reject_reason TEXT;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'task_parse_results'
              AND column_name = 'source_texts'
        ) THEN
            ALTER TABLE task_parse_results ADD COLUMN source_texts JSONB;
        END IF;
    END $$;
    """,
)
