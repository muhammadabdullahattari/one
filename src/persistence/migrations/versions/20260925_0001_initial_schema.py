from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_backends",
        sa.Column("backend_name", sa.String(length=64), nullable=False),
        sa.Column("backend_type", sa.String(length=32), nullable=False),
        sa.Column("connection_config_ref", sa.String(length=256), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="healthy"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("backend_name", name="pk_broker_backends"),
    )
    op.execute(
        sa.text(
            "\n            INSERT INTO broker_backends (backend_name, backend_type, enabled, status)\n            VALUES\n                ('native', 'native', true, 'healthy'),\n                ('redis', 'redis', true, 'healthy'),\n                ('rabbitmq', 'rabbitmq', false, 'disabled'),\n                ('nats', 'nats', false, 'disabled'),\n                ('sqs', 'sqs', false, 'disabled')\n            ON CONFLICT (backend_name) DO NOTHING;\n            "
        )
    )
    op.create_table(
        "queues",
        sa.Column("queue_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_priority", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("rate_limit_rps", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "retry_defaults",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("broker_backend", sa.String(length=64), nullable=False, server_default="native"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["broker_backend"],
            ["broker_backends.backend_name"],
            name="fk_queues_broker_backend",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("queue_name", name="pk_queues"),
    )
    op.execute(
        sa.text(
            "\n            INSERT INTO queues (queue_name, default_priority, max_concurrency, rate_limit_rps, broker_backend)\n            VALUES ('default', 5, 100, 100, 'native')\n            ON CONFLICT (queue_name) DO NOTHING;\n            "
        )
    )
    op.create_table(
        "schedules",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=128), nullable=False),
        sa.Column("queue", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("payload_ref", sa.String(length=512), nullable=True),
        sa.Column("cron_expression", sa.String(length=64), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("misfire_policy", sa.String(length=32), nullable=False, server_default="skip"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("schedule_id", name="pk_schedules"),
    )
    op.create_index("ix_schedules_task_type", "schedules", ["task_type"])
    op.create_index("ix_schedules_enabled", "schedules", ["enabled"])
    op.create_index("ix_schedules_next_run_at", "schedules", ["next_run_at"])
    op.create_index("ix_schedules_due", "schedules", ["enabled", "next_run_at"])
    op.create_table(
        "tasks",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("task_type", sa.String(length=128), nullable=False),
        sa.Column("queue", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload_ref", sa.String(length=512), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_ref", sa.String(length=512), nullable=True),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_worker_id", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_reason", sa.String(length=512), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["queue"], ["queues.queue_name"], name="fk_tasks_queue", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.schedule_id"],
            name="fk_tasks_schedule_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("task_id", name="pk_tasks"),
    )
    op.create_index("ix_tasks_tenant_id", "tasks", ["tenant_id"])
    op.create_index("ix_tasks_task_type", "tasks", ["task_type"])
    op.create_index("ix_tasks_queue", "tasks", ["queue"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_priority", "tasks", ["priority"])
    op.create_index("ix_tasks_idempotency_key", "tasks", ["idempotency_key"])
    op.create_index("ix_tasks_lease_expires_at", "tasks", ["lease_expires_at"])
    op.create_index("ix_tasks_scheduled_at", "tasks", ["scheduled_at"])
    op.create_index("ix_tasks_claim", "tasks", ["queue", "status", "priority", "created_at"])
    op.create_index("ix_tasks_tenant_idempotency", "tasks", ["tenant_id", "idempotency_key"])
    op.create_index(
        "ix_tasks_pending_hotpath",
        "tasks",
        ["queue", "created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_tasks_running_lease_expiry",
        "tasks",
        ["lease_expires_at"],
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    op.create_table(
        "task_attempts",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RUNNING"),
        sa.Column("leased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_class", sa.String(length=256), nullable=True),
        sa.Column("error_message_redacted", sa.Text(), nullable=True),
        sa.Column("result_ref", sa.String(length=512), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name="fk_task_attempts_task_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_task_attempts"),
    )
    op.create_index("ix_task_attempts_task_id", "task_attempts", ["task_id"])
    op.create_index("ix_task_attempts_worker_id", "task_attempts", ["worker_id"])
    op.create_index("ix_task_attempts_task_number", "task_attempts", ["task_id", "attempt_number"])
    op.create_table(
        "task_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.String(length=128), nullable=False, server_default="engine"),
        sa.Column(
            "event_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name="fk_task_events_task_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_task_events"),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_event_type", "task_events", ["event_type"])
    op.create_index("ix_task_events_event_time", "task_events", ["event_time"])
    op.create_index("ix_task_events_timeline", "task_events", ["task_id", "event_time"])
    op.create_table(
        "task_outbox",
        sa.Column("outbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "event_type", sa.String(length=64), nullable=False, server_default="task.created"
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("outbox_id", name="pk_task_outbox"),
    )
    op.create_index("ix_task_outbox_task_id", "task_outbox", ["task_id"])
    op.create_index("ix_task_outbox_created_at", "task_outbox", ["created_at"])
    op.create_index("ix_task_outbox_published_at", "task_outbox", ["published_at"])
    op.create_index("ix_task_outbox_next_attempt_at", "task_outbox", ["next_attempt_at"])
    op.create_index(
        "ix_task_outbox_unpublished",
        "task_outbox",
        ["created_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_table(
        "workers",
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=256), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="0.1.0"),
        sa.Column("protocol_version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column(
            "capabilities_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "queues_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"default\"]'::jsonb"),
        ),
        sa.Column("concurrency", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("active_slots", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("drained_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("worker_id", name="pk_workers"),
    )
    op.create_index("ix_workers_last_heartbeat", "workers", ["last_heartbeat"])
    op.create_table(
        "idempotency_keys",
        sa.Column("scope", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name="fk_idempotency_keys_task_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("scope", "idempotency_key", name="pk_idempotency_keys"),
        sa.UniqueConstraint("scope", "idempotency_key", name="uq_scope_idempotency_key"),
    )
    op.create_index("ix_idempotency_expires", "idempotency_keys", ["expires_at"])
    op.create_table(
        "dlq_entries",
        sa.Column("dlq_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("final_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("error_class", sa.String(length=256), nullable=False),
        sa.Column("payload_ref", sa.String(length=512), nullable=True),
        sa.Column(
            "dead_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("replay_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("dlq_id", name="pk_dlq_entries"),
    )
    op.create_index("ix_dlq_entries_task_id", "dlq_entries", ["task_id"])
    op.create_index("ix_dlq_entries_dead_at", "dlq_entries", ["dead_at"])
    op.create_table(
        "api_credentials",
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="producer"),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("principal_id", name="pk_api_credentials"),
        sa.UniqueConstraint("key_hash", name="uq_api_credentials_key_hash"),
    )
    op.create_index("ix_api_credentials_key_hash", "api_credentials", ["key_hash"])
    op.create_table(
        "audit_events",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="SUCCESS"),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("audit_id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("api_credentials")
    op.drop_table("dlq_entries")
    op.drop_table("idempotency_keys")
    op.drop_table("workers")
    op.drop_table("task_outbox")
    op.drop_table("task_events")
    op.drop_table("task_attempts")
    op.drop_table("tasks")
    op.drop_table("schedules")
    op.drop_table("queues")
    op.drop_table("broker_backends")
