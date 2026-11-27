# Production deployment work in progress

The proposed local topology is browser → unprivileged nginx frontend → FastAPI → existing PostgreSQL and MLflow. The containers are not verified. No production service has been deployed.

Forecast runs and simulated inventory and review records default to local JSON snapshots. An opt-in transactional PostgreSQL record store and a separate migration chain have been implemented but have not passed migration integration testing and have not been deployed. It does not provide cross-process execution locking, resumable chunks, or distributed execution. `/health` is liveness; `/health/ready` probes the configured database but does not establish model readiness. `/metrics` reports process-local request counters, which reset at restart and are not aggregated across workers.

The old Alembic directory has only compiled historical migration artifacts in this workspace. The new `operational_alembic.ini` chain uses its own `decisionos_operational_alembic_version` table and does not stamp the old chain. An attempted isolated-schema test was rejected because the configured database role lacks CREATE SCHEMA; nothing was applied. Verify the new chain in a disposable database before deployment. No migration was applied to the existing database.
