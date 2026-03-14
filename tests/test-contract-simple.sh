#!/bin/bash

# Simple Contract Generation Test with Cookie Handling
BACKEND_URL="http://localhost:3001/api"
COOKIE_FILE="/tmp/test-cookies.txt"

echo "🚀 Starting Contract Generation Test"
echo ""

# Step 1: Login and save cookies
echo "Step 1: Logging in..."
curl -s -c "$COOKIE_FILE" -X POST "${BACKEND_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"testclient@example.com","password":"testpass123"}' \
  > /dev/null

if [ ! -f "$COOKIE_FILE" ]; then
  echo "❌ Failed to save cookies"
  exit 1
fi

echo "✅ User logged in successfully"
echo ""

# Step 2: Create project with contract using saved cookies
echo "Step 2: Creating project with contract..."
RESPONSE=$(curl -s -b "$COOKIE_FILE" -X POST "${BACKEND_URL}/projects/ai-intake" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "John & Sarah Smith",
    "contact_email": "john.sarah@example.com",
    "contact_phone": "+1-555-123-4567",
    "event_type": "wedding",
    "event_date": "2026-06-15",
    "guest_count": 150,
    "service_type": "on_site",
    "venue_name": "Blue Hills House",
    "venue_address": "123 Oak Street, San Francisco, CA 94102",
    "dietary_restrictions": ["vegetarian", "gluten-free"],
    "generate_contract": true
  }')

echo "$RESPONSE"
echo ""

# Extract IDs
PROJECT_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
CONTRACT_STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | grep -v '"statusCode"' | head -1 | cut -d'"' -f4)

if [ -n "$PROJECT_ID" ]; then
  echo "✅ Project created: $PROJECT_ID"
  echo "✅ Contract status: $CONTRACT_STATUS"
  echo ""
  echo "🎯 Next: Login as staff at http://localhost:3002/signin"
  echo "   Then visit: http://localhost:3002/staff/contracts"
else
  echo "❌ Failed to create project"
fi

# Cleanup
rm -f "$COOKIE_FILE"
