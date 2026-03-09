# Manual Setup Guide - Fix Database Issues

## Issue
The automated database seeding is hanging. Follow these manual steps to fix it.

---

## Step 1: Insert Roles Manually

Open your database tool (pgAdmin, DBeaver, or psql) and run:

```sql
-- Clear existing data
DELETE FROM role_permissions;
DELETE FROM user_roles;
DELETE FROM roles;

-- Insert Roles
INSERT INTO roles (id, description, domain) VALUES
('staff', 'FlashBack Labs Staff - Highest authority', 'platform'),
('host', 'Event Host - Can create projects', 'client'),
('collaborator', 'Project Collaborator', 'client');

-- Verify
SELECT * FROM roles ORDER BY id;
```

**Expected Output**:
```
id          | description                              | domain
------------|------------------------------------------|----------
collaborator| Project Collaborator                     | client
host        | Event Host - Can create projects         | client
staff       | FlashBack Labs Staff - Highest authority | platform
```

---

## Step 2: Start Backend

```bash
cd backend
npm run start:dev
```

**Expected**: Server starts on port 3001 without errors

---

## Step 3: Start Frontend

```bash
cd frontend
npm run dev
```

**Expected**: Frontend starts on port 3000

---

## Step 4: Test Signup

### Test A: Staff User
1. Go to: `http://localhost:3000/signup`
2. Fill in:
   ```
   First Name: John
   Last Name: Staff
   Email: john@flashbacklabs.com
   Password: TestPass123
   Phone: +1 (555) 111-2222
   ```
3. Click "Create account"
4. **Expected**: Redirects to `/projects`

### Test B: Host User
1. Logout (click logout button)
2. Go to: `http://localhost:3000/signup`
3. Fill in:
   ```
   First Name: Jane
   Last Name: Host
   Email: jane@gmail.com
   Password: TestPass123
   Phone: +1 (555) 333-4444
   ```
4. Click "Create account"
5. **Expected**: Redirects to `/projects`

---

## Step 5: Verify Database

Run these queries to verify everything worked:

### Check Users
```sql
SELECT id, email, primary_phone, status
FROM users
ORDER BY created_at DESC;
```

**Expected**: See both john@flashbacklabs.com and jane@gmail.com with phone numbers

### Check User Roles
```sql
SELECT u.email, ur.role_id, ur.scope_type
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
ORDER BY u.created_at DESC;
```

**Expected**:
```
email                      | role_id | scope_type
---------------------------|---------|------------
jane@gmail.com            | host    | global
john@flashbacklabs.com    | staff   | global
```

### Check User Profiles
```sql
SELECT u.email, up.profile_type, up.metadata
FROM users u
JOIN user_profiles up ON u.id = up.user_id
ORDER BY u.created_at DESC;
```

**Expected**:
```
email                      | profile_type  | metadata
---------------------------|---------------|---------------------------
jane@gmail.com            | event_host    | {"first_name":"Jane","last_name":"Host"}
john@flashbacklabs.com    | staff_member  | {"first_name":"John","last_name":"Staff"}
```

---

## Step 6: Test Route Protection

### Protected Routes Test
1. Open incognito/private window
2. Try to go to: `http://localhost:3000/projects`
3. **Expected**: Redirected to `/signin?redirect=/projects`

### Auth Routes Test
1. Login as `jane@gmail.com`
2. Try to go to: `http://localhost:3000/signin`
3. **Expected**: Redirected to `/projects`

---

## Troubleshooting

### If Backend Won't Start
```bash
cd backend
npm run build
```

Look for errors. Most common:
- **TypeScript errors**: Check the error message
- **Database connection**: Verify DATABASE_URL in `.env`
- **Port in use**: Kill process on port 3001

### If Users Created But No Roles
Check if transaction failed:
```sql
-- See if users exist but roles don't
SELECT u.email, ur.role_id
FROM users u
LEFT JOIN user_roles ur ON u.id = ur.user_id
WHERE ur.role_id IS NULL;
```

If users exist without roles, the transaction failed. Delete those users and try again:
```sql
DELETE FROM users WHERE email IN ('john@flashbacklabs.com', 'jane@gmail.com');
```

### If Primary Phone Not Saving
Check the column exists:
```sql
\d users
```

Look for `primary_phone` column. If it's not there, the schema is wrong.

### Backend Errors
Check backend terminal for errors like:
- `Foreign key constraint failed` → Roles don't exist
- `Column does not exist` → Schema mismatch
- `Timeout` → Database connection issue

---

## Quick Verification Script

Run this all at once to verify everything:

```sql
-- 1. Check roles exist
SELECT 'Roles Check:' as test;
SELECT id FROM roles WHERE id IN ('staff', 'host', 'collaborator');

-- 2. Check users
SELECT 'Users Check:' as test;
SELECT email, primary_phone FROM users ORDER BY created_at DESC LIMIT 5;

-- 3. Check user roles
SELECT 'User Roles Check:' as test;
SELECT u.email, ur.role_id
FROM users u
LEFT JOIN user_roles ur ON u.id = ur.user_id
ORDER BY u.created_at DESC LIMIT 5;

-- 4. Check profiles
SELECT 'Profiles Check:' as test;
SELECT u.email, up.profile_type
FROM users u
LEFT JOIN user_profiles up ON u.id = up.user_id
ORDER BY u.created_at DESC LIMIT 5;
```

---

## Success Criteria

✅ Backend starts without errors
✅ Frontend starts without errors
✅ Can signup with staff email → gets `staff` role
✅ Can signup with regular email → gets `host` role
✅ Primary phone is saved in database
✅ User profiles created with metadata
✅ Protected routes redirect to signin
✅ Can't access signin/signup while logged in

---

## Next Steps After Verification

Once everything above works:
1. Test creating a project
2. Test adding collaborators (future feature)
3. Integrate chat with AI models
4. Implement contract creation flow

