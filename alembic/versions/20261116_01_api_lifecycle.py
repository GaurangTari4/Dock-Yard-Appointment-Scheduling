"""api lifecycle and immutable event history"""
from alembic import op
revision='20261116_01'; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    op.execute("ALTER TABLE appointments DROP CONSTRAINT appointments_status_check")
    op.execute("ALTER TABLE appointments ADD CONSTRAINT appointments_status_check CHECK (status IN ('REQUESTED','CONFIRMED','SCHEDULED','WAITLISTED','ARRIVED','CHECKED_IN','IN_SERVICE','COMPLETED','DEPARTED','CANCELLED','RESCHEDULED','NO_SHOW'))")
    op.execute("CREATE TABLE appointment_state_events (event_id bigserial PRIMARY KEY, appointment_id varchar(24) NOT NULL REFERENCES appointments, event_type text NOT NULL, event_ts timestamptz NOT NULL, actor text NOT NULL, source text NOT NULL, rule_version text NOT NULL, decision_provenance jsonb NOT NULL DEFAULT '{}'::jsonb)")
    op.execute("CREATE INDEX ix_state_events_appointment_time ON appointment_state_events(appointment_id,event_ts)")
    op.execute("ALTER TABLE dock_reservations DROP CONSTRAINT dock_reservations_appointment_id_key")
    op.execute("ALTER TABLE yard_reservations DROP CONSTRAINT yard_reservations_appointment_id_key")
    op.execute("ALTER TABLE labor_allocations DROP CONSTRAINT labor_allocations_appointment_id_key")
def downgrade():
    op.execute('DROP TABLE appointment_state_events')
