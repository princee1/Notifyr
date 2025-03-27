-- FROM Chat GPT

-- Check current max_connections
SHOW max_connections;

-- Check current work memory
SHOW work_mem;

-- Check shared buffers
SHOW shared_buffers;

-- Check effective cache size
SHOW effective_cache_size;

-- Check WAL settings
SHOW wal_buffers;
SHOW checkpoint_timeout;
SHOW checkpoint_completion_target;
SHOW synchronous_commit;

-- Check autovacuum settings
SHOW autovacuum_vacuum_cost_limit;
SHOW autovacuum_vacuum_cost_delay;

-- Check vacuum activity (dead tuples, last vacuum)
SELECT relname, last_autovacuum, last_analyze FROM pg_stat_user_tables;

-- Check current database connections
SELECT * FROM pg_stat_activity;

-- Adjust PostgreSQL settings (requires postgresql.conf update)
-- WARNING: These changes should be made in postgresql.conf manually and require a restart.

-- Recommended changes to postgresql.conf (DO NOT RUN DIRECTLY in SQL):
-- max_connections = 300
-- shared_buffers = 4GB
-- work_mem = 16MB
-- effective_cache_size = 8GB
-- wal_buffers = 16MB
-- checkpoint_timeout = 10min
-- checkpoint_completion_target = 0.9
-- synchronous_commit = off
-- bgwriter_lru_maxpages = 200
-- bgwriter_lru_multiplier = 4.0
-- autovacuum_vacuum_cost_limit = 2000
-- autovacuum_vacuum_cost_delay = 10ms
