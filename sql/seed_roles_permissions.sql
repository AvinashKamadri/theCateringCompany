-- Seed Roles and Permissions
-- Run this to set up the role hierarchy

-- Clear existing data (optional - remove if you want to keep existing roles)
DELETE FROM role_permissions;
DELETE FROM roles;

-- Insert Roles
INSERT INTO roles (id, description, domain) VALUES
('staff', 'FlashBack Labs Staff - Highest authority, can approve contracts', 'platform'),
('host', 'Event Host - Can create projects, manage collaborators, trigger contract wrap-up', 'client'),
('collaborator', 'Project Collaborator - Can view and participate in assigned projects', 'client')
ON CONFLICT (id) DO UPDATE SET
  description = EXCLUDED.description,
  domain = EXCLUDED.domain;

-- Insert Role Permissions

-- STAFF Permissions (Highest Authority)
INSERT INTO role_permissions (role_id, permission, created_at) VALUES
('staff', 'projects.view_all', NOW()),
('staff', 'projects.create', NOW()),
('staff', 'projects.update', NOW()),
('staff', 'projects.delete', NOW()),
('staff', 'contracts.view', NOW()),
('staff', 'contracts.create', NOW()),
('staff', 'contracts.update', NOW()),
('staff', 'contracts.approve', NOW()),  -- Only staff can approve contracts
('staff', 'contracts.delete', NOW()),
('staff', 'users.view', NOW()),
('staff', 'users.manage', NOW()),
('staff', 'messages.view', NOW()),
('staff', 'messages.send', NOW()),
('staff', 'crm.view', NOW()),
('staff', 'crm.manage', NOW()),
('staff', 'payments.view', NOW()),
('staff', 'payments.manage', NOW())
ON CONFLICT (role_id, permission) DO NOTHING;

-- HOST Permissions (Event Owners)
INSERT INTO role_permissions (role_id, permission, created_at) VALUES
('host', 'projects.create', NOW()),
('host', 'projects.view_own', NOW()),
('host', 'projects.update_own', NOW()),
('host', 'projects.delete_own', NOW()),
('host', 'collaborators.add', NOW()),      -- Host can add collaborators
('host', 'collaborators.remove', NOW()),    -- Host can remove collaborators
('host', 'contracts.view_own', NOW()),
('host', 'contracts.trigger_wrapup', NOW()), -- Only host can trigger contract wrap-up
('host', 'messages.view_own', NOW()),
('host', 'messages.send', NOW()),
('host', 'payments.view_own', NOW()),
('host', 'crm.view_own', NOW())
ON CONFLICT (role_id, permission) DO NOTHING;

-- COLLABORATOR Permissions (Invited Team Members)
INSERT INTO role_permissions (role_id, permission, created_at) VALUES
('collaborator', 'projects.view_assigned', NOW()),
('collaborator', 'contracts.view_assigned', NOW()),
('collaborator', 'messages.view_assigned', NOW()),
('collaborator', 'messages.send', NOW())
ON CONFLICT (role_id, permission) DO NOTHING;

-- Verify the inserts
SELECT 'Roles Inserted:' as info;
SELECT * FROM roles ORDER BY domain, id;

SELECT 'Role Permissions Inserted:' as info;
SELECT r.id as role, r.description, COUNT(rp.permission) as permission_count
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
GROUP BY r.id, r.description
ORDER BY r.domain, r.id;

SELECT 'Detailed Permissions:' as info;
SELECT r.id as role, rp.permission
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
ORDER BY r.id, rp.permission;
