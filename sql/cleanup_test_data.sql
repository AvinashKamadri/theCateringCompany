-- Cleanup Test Data Script
-- Run this to clear all test users and related data

\set ON_ERROR_STOP on

-- Delete in reverse order of foreign key dependencies
DELETE FROM message_mentions WHERE mentioned_user_id IN (SELECT id FROM users);
DELETE FROM messages WHERE author_id IN (SELECT id FROM users);
DELETE FROM sessions WHERE user_id IN (SELECT id FROM users);
DELETE FROM project_collaborators WHERE user_id IN (SELECT id FROM users);
DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users);
DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users);
DELETE FROM users;

-- Verify cleanup
SELECT 'Users remaining:' as status, COUNT(*) as count FROM users;
SELECT 'User roles remaining:' as status, COUNT(*) as count FROM user_roles;
SELECT 'User profiles remaining:' as status, COUNT(*) as count FROM user_profiles;
SELECT 'Sessions remaining:' as status, COUNT(*) as count FROM sessions;

-- Verify roles are still present
SELECT 'Roles Check:' as status;
SELECT * FROM roles ORDER BY id;
