# Database Seeding Guide

This guide explains how to seed your database with test users, menu items, and pricing packages.

---

## Prerequisites

✅ Database is running
✅ Roles exist in database (staff, host, collaborator)
✅ Backend dependencies installed

---

## Quick Start

### 1. Ensure Roles Exist

First, verify roles are in the database:

```bash
psql -U postgres -d caterDB_prod -c "SELECT * FROM roles ORDER BY id;"
```

**Expected output:**
```
id          | description                              | domain
------------|------------------------------------------|----------
collaborator| Project Collaborator                     | client
host        | Event Host - Can create projects         | client
staff       | FlashBack Labs Staff - Highest authority | platform
```

**If roles are missing**, run:
```bash
psql -U postgres -d caterDB_prod -f sql/quick_setup.sql
```

---

### 2. Run the Seeding Script

```bash
cd backend
npm run seed:users
```

This will create:
- **20 staff users** (emails ending with @flashbacklabs.com)
- **80 host users** (emails from various domains like @gmail.com, @yahoo.com, etc.)

**Total: 100 users**

---

## What Gets Created

For each user, the script creates:

1. **User record** in `users` table
   - Email (unique)
   - Password hash (all use: `TestPass123`)
   - Primary phone
   - Status: `active`

2. **User profile** in `user_profiles` table
   - Profile type: `staff` or `client`
   - Metadata: `{first_name, last_name}`

3. **User role** in `user_roles` table
   - Role ID: `staff` or `host`
   - Scope: `global`

---

## Default Credentials

**All seeded users have the same password:**
```
Password: TestPass123
```

**Sample Staff User:**
```
Email: john.smith.0@flashbacklabs.com
Password: TestPass123
Role: staff
```

**Sample Host User:**
```
Email: mary.jones.0@gmail.com
Password: TestPass123
Role: host
```

---

## Seeding Output

The script shows progress and provides a summary:

```
🌱 Starting user seeding...

Creating 20 staff users...
✓ 20 staff users created

Creating 80 host users...
✓ 80 host users created

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Seeding Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Staff users:  20/20
✅ Host users:   80/80
❌ Errors:       0
📧 Total users:  100/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔐 Default password for all users: TestPass123

📝 Sample login credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Staff User:
  Name: John Smith
  Email: john.smith.0@flashbacklabs.com
  Password: TestPass123

Host User:
  Name: Mary Jones
  Email: mary.jones.0@gmail.com
  Password: TestPass123
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Verify Seeding

After seeding, verify the data:

```sql
-- Count users by role
SELECT r.id as role, COUNT(*) as count
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
GROUP BY r.id
ORDER BY r.id;
```

**Expected:**
```
role          | count
--------------|-------
host          | 80
staff         | 20
```

---

## Check User Profiles

```sql
-- Check profiles
SELECT up.profile_type, COUNT(*) as count
FROM user_profiles up
GROUP BY up.profile_type
ORDER BY up.profile_type;
```

**Expected:**
```
profile_type  | count
--------------|-------
client        | 80
staff         | 20
```

---

## View Sample Users

```sql
-- View 5 staff users
SELECT
  u.email,
  u.primary_phone,
  up.profile_type,
  up.metadata,
  ur.role_id
FROM users u
JOIN user_profiles up ON u.id = up.user_id
JOIN user_roles ur ON u.id = ur.user_id
WHERE u.email LIKE '%@flashbacklabs.com'
LIMIT 5;
```

```sql
-- View 5 host users
SELECT
  u.email,
  u.primary_phone,
  up.profile_type,
  up.metadata,
  ur.role_id
FROM users u
JOIN user_profiles up ON u.id = up.user_id
JOIN user_roles ur ON u.id = ur.user_id
WHERE u.email NOT LIKE '%@flashbacklabs.com'
LIMIT 5;
```

---

## Test Login

1. Go to `http://localhost:3000/signin`
2. Use any seeded user email (e.g., `john.smith.0@flashbacklabs.com`)
3. Password: `TestPass123`
4. Should redirect to `/projects`

---

## Clean Up Seeded Data

If you want to remove all seeded users:

```sql
-- Delete all users and related data
DELETE FROM message_mentions WHERE mentioned_user_id IN (SELECT id FROM users);
DELETE FROM messages WHERE author_id IN (SELECT id FROM users);
DELETE FROM sessions WHERE user_id IN (SELECT id FROM users);
DELETE FROM project_collaborators WHERE user_id IN (SELECT id FROM users);
DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users);
DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users);
DELETE FROM users;

-- Verify cleanup
SELECT COUNT(*) FROM users;  -- Should return 0
```

Or use the cleanup script:
```bash
psql -U postgres -d caterDB_prod -f sql/cleanup_test_data.sql
```

---

## Customizing the Seed Data

To change the number of users or modify the seed data, edit:
```
backend/src/scripts/seed-users.ts
```

Key variables:
- Line 14-24: `firstNames` array
- Line 26-36: `lastNames` array
- Line 38-42: `emailDomains` array
- Line 82: Change `20` to adjust staff user count
- Line 131: Change `80` to adjust host user count

---

## Troubleshooting

### Error: "No roles found in database"

**Solution:** Run the roles seed script first:
```bash
psql -U postgres -d caterDB_prod -f sql/quick_setup.sql
```

---

### Error: "Email already in use"

**Cause:** You've run the seed script multiple times.

**Solution:** The script will skip duplicate emails. If you want fresh data, clean up first:
```bash
psql -U postgres -d caterDB_prod -f sql/cleanup_test_data.sql
npm run seed:users
```

---

### Error: "ConnectorError: Connection refused"

**Cause:** Database is not running.

**Solution:** Start your PostgreSQL database and verify connection:
```bash
psql -U postgres -d caterDB_prod -c "SELECT 1;"
```

---

## Next Steps

After seeding:

1. ✅ Test login with seeded users
2. ✅ Test role-based access (staff vs host)
3. ✅ Create test projects as different users
4. ✅ Test collaborator workflows

---

## Summary

| Metric | Value |
|--------|-------|
| Total Users | 100 |
| Staff Users | 20 |
| Host Users | 80 |
| Default Password | TestPass123 |
| Profile Types | `staff` (20), `client` (80) |
| Roles | `staff` (20), `host` (80) |

All users have:
- Unique email addresses
- Random first and last names
- Random phone numbers
- Active status
- Complete profile with metadata
- Assigned role (global scope)

---

## Menu & Pricing Seeding

### Seed Menu Items

To populate the menu catalog with real catering menu items:

```bash
cd backend
npm run seed:menu
```

This will create:
- **19 menu categories** (Hors D'oeuvres, Platters, Signature Combinations, BBQ, Casual Fare, Mexican, Mediterranean, Italian, Soup/Salad, Potato Bar, Desserts, Wedding Cakes, Floral Arrangements)
- **100+ menu items** with realistic pricing
- **6 pricing packages** (Bronze, Silver, Gold, Platinum, Wedding Basic, Wedding Deluxe)

### Menu Categories Created

1. **Hors D'oeuvres** - Beef ($3.50 pp)
2. **Hors D'oeuvres** - Chicken ($3.50 pp)
3. **Hors D'oeuvres** - Pork ($3.50 pp)
4. **Hors D'oeuvres** - Seafood ($3.50-$4.75 pp)
5. **Hors D'oeuvres** - Vegetarian ($1.25-$2.75 pp)
6. **Hors D'oeuvres** - Canapes ($2.00-$4.00 pp)
7. **Platters** ($2.25-$4.25 pp)
8. **Signature Combinations** ($27.99-$39.99 pp)
9. **BBQ Menus** ($23.99-$25.99 pp)
10. **Casual Fare** - Burger Bar & Southern Comfort ($23.99-$27.95 pp)
11. **Mexican** ($23.99-$27.99 pp)
12. **Mediterranean Bars** ($21.49-$23.49 pp)
13. **Italian Bars** ($21.99-$31.99 pp)
14. **Soup/Salad/Sandwich** ($21.95 pp)
15. **Potato Bar** ($19.95 pp)
16. **Coffee and Desserts** ($2.75-$5.25 pp)
17. **Wedding Cakes** ($275 flat)
18. **Floral Arrangements** ($15-$150 flat)

### Pricing Packages Created

| Package | Category | Price | Type |
|---------|----------|-------|------|
| Bronze Package | Standard | $20.00 | per_person |
| Silver Package | Standard | $25.00 | per_person |
| Gold Package | Premium | $35.00 | per_person |
| Platinum Package | Premium | $50.00 | per_person |
| Wedding Package - Basic | Wedding | $45.00 | per_person |
| Wedding Package - Deluxe | Wedding | $65.00 | per_person |

### Verify Menu Data

```sql
-- Count menu categories
SELECT COUNT(*) as category_count FROM menu_categories;
-- Should return: 19

-- Count menu items
SELECT COUNT(*) as item_count FROM menu_items;
-- Should return: 100+

-- View categories with item counts
SELECT
  mc.name,
  COUNT(mi.id) as item_count,
  MIN(mi.unit_price) as min_price,
  MAX(mi.unit_price) as max_price
FROM menu_categories mc
LEFT JOIN menu_items mi ON mc.id = mi.category_id
GROUP BY mc.id, mc.name
ORDER BY mc.sort_order;
```

### Sample Menu Items

```sql
-- View hors d'oeuvres
SELECT name, unit_price, price_type, tags
FROM menu_items mi
JOIN menu_categories mc ON mi.category_id = mc.id
WHERE mc.name LIKE '%Hors D%'
LIMIT 10;

-- View vegetarian items
SELECT name, unit_price, mc.name as category
FROM menu_items mi
JOIN menu_categories mc ON mi.category_id = mc.id
WHERE 'vegetarian' = ANY(mi.tags)
ORDER BY unit_price;
```

### Clean Up Menu Data

If you want to remove all menu data:

```sql
-- Delete all menu items and categories
DELETE FROM menu_items;
DELETE FROM menu_categories;
DELETE FROM pricing_packages;

-- Verify cleanup
SELECT COUNT(*) FROM menu_items;  -- Should return 0
SELECT COUNT(*) FROM menu_categories;  -- Should return 0
SELECT COUNT(*) FROM pricing_packages;  -- Should return 0
```

---

## Complete Seeding Workflow

To seed everything from scratch:

```bash
# 1. Clean up (if needed)
psql -U postgres -d caterDB_prod -f sql/cleanup_test_data.sql

# 2. Ensure roles exist
psql -U postgres -d caterDB_prod -c "SELECT * FROM roles;"

# 3. Seed users (100 users)
cd backend
npm run seed:users

# 4. Seed menu and pricing
npm run seed:menu

# 5. Verify everything
psql -U postgres -d caterDB_prod -c "
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM menu_categories) as categories,
  (SELECT COUNT(*) FROM menu_items) as menu_items,
  (SELECT COUNT(*) FROM pricing_packages) as packages;
"
```

Expected output:
```
users | categories | menu_items | packages
------|------------|------------|----------
100   | 19         | 100+       | 6
```
