# Troubleshooting Guide - Signup Transaction Issue

## Current Problem
Users are being created but `user_roles` and `user_profiles` tables remain empty (0 rows). This indicates the Prisma transaction is failing partially.

---

## Step-by-Step Fix

### 1. Clean Up Test Data

Run this in your database tool (pgAdmin, DBeaver, or psql):

```sql
-- Run the cleanup script
\i c:/Users/avina/projects/flashback/cateringCo/sql/cleanup_test_data.sql

-- Or run manually:
DELETE FROM message_mentions WHERE mentioned_user_id IN (SELECT id FROM users);
DELETE FROM messages WHERE author_id IN (SELECT id FROM users);
DELETE FROM sessions WHERE user_id IN (SELECT id FROM users);
DELETE FROM project_collaborators WHERE user_id IN (SELECT id FROM users);
DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users);
DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users);
DELETE FROM users;

-- Verify cleanup
SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as roles_count FROM user_roles;
SELECT COUNT(*) as profiles_count FROM user_profiles;

-- Should all return 0
```

---

### 2. Verify Roles Exist

```sql
SELECT * FROM roles ORDER BY id;
```

**Expected Output:**
```
id          | description                              | domain
------------|------------------------------------------|----------
collaborator| Project Collaborator                     | client
host        | Event Host - Can create projects         | client
staff       | FlashBack Labs Staff - Highest authority | platform
```

**If roles are missing**, run:
```sql
\i c:/Users/avina/projects/flashback/cateringCo/sql/quick_setup.sql
```

---

### 3. Check Table Permissions

Ensure the database user has INSERT permissions on all tables:

```sql
-- Check current user
SELECT current_user;

-- Grant all permissions (replace 'avinash' with your DB user)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO avinash;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO avinash;
```

---

### 4. Restart Backend with Logging

The backend has been updated with detailed transaction logging. Restart it:

```bash
cd backend
npm run start:dev
```

Watch the console for detailed logs showing each step of the transaction.

---

### 5. Test Signup

#### Option A: Using Frontend
1. Go to `http://localhost:3000/signup`
2. Fill in:
   - First Name: **John**
   - Last Name: **Staff**
   - Email: **john@flashbacklabs.com**
   - Password: **TestPass123**
   - Phone: **+1 (555) 111-2222**
3. Click "Create account"

#### Option B: Using curl
```bash
curl -X POST http://localhost:3001/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@flashbacklabs.com",
    "password": "TestPass123",
    "primary_phone": "+1 (555) 111-2222",
    "first_name": "John",
    "last_name": "Staff"
  }'
```

---

### 6. Check Backend Console

You should see detailed logs like:

```
=== TRANSACTION START ===
Email: john@flashbacklabs.com
Role to assign: staff
Profile type: staff_member
Profile data: { primary_phone: '+1 (555) 111-2222', first_name: 'John', last_name: 'Staff' }
Step 1: Creating user...
User created with ID: <uuid>
Step 2: Creating user profile...
User profile created with ID: <uuid>
Step 3: Assigning role...
Role assigned with ID: <uuid>
=== TRANSACTION SUCCESS ===
```

**If you see `=== TRANSACTION ERROR ===`**, the error details will show the exact problem.

---

### 7. Verify Database After Signup

```sql
-- Check user was created
SELECT id, email, primary_phone, status FROM users ORDER BY created_at DESC LIMIT 1;

-- Check profile was created
SELECT up.id, up.user_id, up.profile_type, up.metadata
FROM user_profiles up
JOIN users u ON up.user_id = u.id
ORDER BY up.created_at DESC LIMIT 1;

-- Check role was assigned
SELECT ur.id, u.email, ur.role_id, ur.scope_type
FROM user_roles ur
JOIN users u ON ur.user_id = u.id
ORDER BY ur.created_at DESC LIMIT 1;
```

**Expected Results:**
- 1 user with email, phone, status = 'active'
- 1 profile with profile_type = 'staff_member', metadata = {"first_name":"John","last_name":"Staff"}
- 1 user_role with role_id = 'staff', scope_type = 'global'

---

## Common Errors and Solutions

### Error: `Foreign key constraint failed on role_id`

**Cause**: Roles don't exist in the database.

**Fix**: Run the roles seed script:
```sql
\i c:/Users/avina/projects/flashback/cateringCo/sql/quick_setup.sql
```

---

### Error: `Permission denied for table user_roles` or `user_profiles`

**Cause**: Database user doesn't have INSERT permissions.

**Fix**:
```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO avinash;
```

---

### Error: `Invalid value for enum scope_type`

**Cause**: Prisma enum doesn't match database enum.

**Fix**:
```bash
cd backend
npx prisma db pull --force
npx prisma generate
npm run build
```

---

### Error: `Column 'profile_type' does not exist`

**Cause**: Database schema doesn't match Prisma schema.

**Fix**: Check database schema:
```sql
\d user_profiles
```

Should show `profile_type` column. If not, the schema is wrong.

---

## Success Criteria

✅ Backend starts without errors
✅ Signup succeeds (no 500 error)
✅ Backend logs show `=== TRANSACTION SUCCESS ===`
✅ Database shows 1 row in `users`
✅ Database shows 1 row in `user_profiles`
✅ Database shows 1 row in `user_roles`
✅ `primary_phone` is saved correctly
✅ Staff email gets `staff` role
✅ Frontend redirects to `/projects` after signup

---

## Next Steps After Fix

Once signup is working:

1. **Test with host user**:
   - Email: `jane@gmail.com`
   - Should get `host` role
   - Profile type should be `event_host`

2. **Test route protection**:
   - Try accessing `/projects` without login (should redirect to signin)
   - Try accessing `/signin` while logged in (should redirect to projects)

3. **Test projects page**:
   - Should load (even if empty)
   - No console errors
   - Can create a project

---

## If Still Failing

If the transaction is still failing after all steps above:

1. **Check backend logs** for the exact error message after `=== TRANSACTION ERROR ===`
2. **Check database constraints**:
   ```sql
   SELECT conname, contype, conrelid::regclass
   FROM pg_constraint
   WHERE conrelid IN ('users'::regclass, 'user_roles'::regclass, 'user_profiles'::regclass);
   ```
3. **Try manual insert** to isolate the issue:
   ```sql
   -- Insert test user
   INSERT INTO users (email, password_hash, primary_phone, status)
   VALUES ('test@test.com', 'hash', '+1234567890', 'active')
   RETURNING id;

   -- Use the returned ID to insert profile
   INSERT INTO user_profiles (user_id, profile_type, metadata)
   VALUES ('<user-id-from-above>', 'staff_member', '{"first_name":"Test","last_name":"User"}')
   RETURNING id;

   -- Use the user ID to insert role
   INSERT INTO user_roles (user_id, role_id, scope_type, scope_id)
   VALUES ('<user-id-from-above>', 'staff', 'global', NULL)
   RETURNING id;
   ```

If manual insert fails, the error will show the exact constraint/issue.
