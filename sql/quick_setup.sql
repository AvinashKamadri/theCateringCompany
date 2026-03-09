-- Quick Setup: Insert Roles Only
\set ON_ERROR_STOP on

-- Delete existing roles if any
DELETE FROM role_permissions WHERE role_id IN ('staff', 'host', 'collaborator');
DELETE FROM roles WHERE id IN ('staff', 'host', 'collaborator');

-- Insert Roles
INSERT INTO roles (id, description, domain) VALUES
('staff', 'FlashBack Labs Staff', 'platform'),
('host', 'Event Host', 'client'),
('collaborator', 'Project Collaborator', 'client');

-- Verify
SELECT 'Roles created:' as status;
SELECT * FROM roles WHERE id IN ('staff', 'host', 'collaborator');
