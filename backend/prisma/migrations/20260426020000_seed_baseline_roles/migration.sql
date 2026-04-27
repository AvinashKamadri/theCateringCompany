-- Baseline RBAC roles. Previously lived in sql/quick_setup.sql, which was a
-- manual post-reset step. Folding it into migration history makes
-- `prisma migrate reset` self-healing — no human in the loop.
--
-- Idempotent: ON CONFLICT DO NOTHING so re-runs and partially-seeded DBs are
-- safe. Description/domain are static and treated as fixed identity here.

INSERT INTO "roles" ("id", "description", "domain") VALUES
  ('staff',        'FlashBack Labs Staff', 'platform'),
  ('host',         'Event Host',           'client'),
  ('collaborator', 'Project Collaborator', 'client')
ON CONFLICT ("id") DO NOTHING;
