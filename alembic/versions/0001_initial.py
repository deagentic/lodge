"""Initial schema: events table and mv_summary materialized view.

Revision ID: 0001
Revises:
Create Date: 2026-03-17
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type      TEXT NOT NULL,
            project_slug    TEXT NOT NULL,
            github_username TEXT NOT NULL DEFAULT '',
            schema_version  TEXT NOT NULL DEFAULT '1.0',
            received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            event_ts        TIMESTAMPTZ NOT NULL,
            payload         JSONB NOT NULL
        )
    """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_event_type   ON events (event_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_project_slug ON events (project_slug)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_received_at  ON events (received_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_type_project ON events (event_type, project_slug)"
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_summary AS
        SELECT
            project_slug,
            event_type,
            date_trunc('day', event_ts) AS day,
            count(*) AS event_count,
            sum((payload->>'estimated_cost_usd')::float)
                FILTER (WHERE event_type = 'skill.invoked') AS daily_cost_usd
        FROM events
        GROUP BY project_slug, event_type, day
    """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_summary_pk
        ON mv_summary (project_slug, event_type, day)
    """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary")
    op.execute("DROP TABLE IF EXISTS events")
