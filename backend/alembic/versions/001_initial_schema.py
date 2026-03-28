"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE projectstatus AS ENUM (
                'pending','running','waiting_review',
                'completed','failed','cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE runstatus AS ENUM (
                'pending','running','waiting_review',
                'completed','failed','cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── projects ───────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name",             sa.String(255),  nullable=False),
        sa.Column("description",      sa.Text(),       nullable=False),
        sa.Column("requirements",     sa.Text(),       nullable=False),
        sa.Column("target_language",  sa.String(50),   nullable=False),
        sa.Column("target_framework", sa.String(100),  nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "waiting_review",
                "completed", "failed", "cancelled",
                name="projectstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_projects_created_at", "projects", ["created_at"])
    op.create_index("ix_projects_status",     "projects", ["status"])

    # ── project_runs ───────────────────────────────────────────────────────
    op.create_table(
        "project_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thread_id",         sa.String(255),  nullable=False, unique=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "waiting_review",
                "completed", "failed", "cancelled",
                name="runstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("current_step",      sa.String(100),  nullable=True),
        sa.Column(
            "interrupt_payload",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message",     sa.Text(),       nullable=True),
        sa.Column("started_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_project_runs_project_id",  "project_runs", ["project_id"])
    op.create_index("ix_project_runs_created_at",  "project_runs", ["created_at"])
    op.create_index("ix_project_runs_status",      "project_runs", ["status"])

    # ── run_events ─────────────────────────────────────────────────────────
    op.create_table(
        "run_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("step",       sa.String(100), nullable=True),
        sa.Column("message",    sa.Text(),       nullable=False),
        sa.Column(
            "data",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_run_events_run_id",     "run_events", ["run_id"])
    op.create_index("ix_run_events_created_at", "run_events", ["created_at"])
    op.create_index("ix_run_events_event_type", "run_events", ["event_type"])

    # ── artifacts ──────────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name",          sa.String(255),  nullable=False),
        sa.Column("artifact_type", sa.String(50),   nullable=False),
        sa.Column("s3_key",        sa.String(1024), nullable=False),
        sa.Column("file_path",     sa.String(1024), nullable=False),
        sa.Column("language",      sa.String(50),   nullable=True),
        sa.Column("size_bytes",    sa.Integer(),    nullable=True),
        sa.Column(
            "is_approved",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_run_id",     "artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_artifacts_run_id",        "artifacts")
    op.drop_index("ix_artifacts_project_id",    "artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_run_events_event_type",   "run_events")
    op.drop_index("ix_run_events_created_at",   "run_events")
    op.drop_index("ix_run_events_run_id",       "run_events")
    op.drop_table("run_events")

    op.drop_index("ix_project_runs_status",     "project_runs")
    op.drop_index("ix_project_runs_created_at", "project_runs")
    op.drop_index("ix_project_runs_project_id", "project_runs")
    op.drop_table("project_runs")

    op.drop_index("ix_projects_status",         "projects")
    op.drop_index("ix_projects_created_at",     "projects")
    op.drop_table("projects")

    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS projectstatus")
