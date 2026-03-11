#!/bin/bash

# Complete End-to-End Flow Test
# Tests: Contract Generation → Staff Approval → SignWell

echo "🚀 Starting Complete End-to-End Flow Test"
echo "=========================================="

BACKEND_URL="http://localhost:3001/api"
CLIENT_EMAIL="testclient@example.com"
CLIENT_PASS="Avinash@1617"
STAFF_EMAIL="avinash@flashbacklabs.com"
STAFF_PASS="Avinash@1617"

# Step 1: Create/Login Client
echo ""
echo "📝 Step 1: Creating client account..."

CLIENT_RESPONSE=$(curl -s -c client_cookies.txt -X POST "${BACKEND_URL}/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${CLIENT_EMAIL}\",
    \"password\": \"${CLIENT_PASS}\",
    \"first_name\": \"Test\",
    \"last_name\": \"Client\",
    \"primary_phone\": \"555-1234\"
  }")

if echo "$CLIENT_RESPONSE" | grep -q "error"; then
  echo "ℹ️  Account exists, logging in..."
  curl -s -c client_cookies.txt -X POST "${BACKEND_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"${CLIENT_EMAIL}\", \"password\": \"${CLIENT_PASS}\"}" > /dev/null
fi

echo "✅ Client authenticated"

# Step 2: Create/Login Staff
echo ""
echo "📝 Step 2: Creating staff account..."

STAFF_RESPONSE=$(curl -s -c staff_cookies.txt -X POST "${BACKEND_URL}/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"${STAFF_EMAIL}\",
    \"password\": \"${STAFF_PASS}\",
    \"first_name\": \"Staff\",
    \"last_name\": \"Admin\"
  }")

if echo "$STAFF_RESPONSE" | grep -q "error"; then
  echo "ℹ️  Staff account exists, logging in..."
  curl -s -c staff_cookies.txt -X POST "${BACKEND_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"${STAFF_EMAIL}\", \"password\": \"${STAFF_PASS}\"}" > /dev/null
fi

echo "✅ Staff authenticated"

# Step 3: Generate Contract
echo ""
echo "🤖 Step 3: Generating contract..."

CONTRACT_RESPONSE=$(curl -s -b client_cookies.txt -X POST "${BACKEND_URL}/projects/ai-intake" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "John Doe",
    "contact_email": "john.doe@example.com",
    "contact_phone": "555-9876",
    "event_type": "Wedding",
    "event_date": "2026-06-15",
    "guest_count": 150,
    "service_type": "Full Service",
    "venue_name": "Grand Ballroom",
    "venue_address": "123 Main St, City, State 12345",
    "menu_items": ["Chicken Breast", "Grilled Salmon"],
    "dietary_restrictions": ["Vegetarian options"],
    "budget_range": "$5000-$8000",
    "generate_contract": true
  }')

PROJECT_ID=$(echo "$CONTRACT_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
CONTRACT_ID=$(echo "$CONTRACT_RESPONSE" | grep -o '"id":"[^"]*"' | sed -n '2p' | cut -d'"' -f4)

echo "✅ Project ID: $PROJECT_ID"
echo "✅ Contract ID: $CONTRACT_ID"
echo "$CONTRACT_RESPONSE" | python -m json.tool 2>/dev/null | head -30

# Step 4: Get Pending Contracts (as staff)
echo ""
echo "📊 Step 4: Fetching pending contracts (as staff)..."

sleep 2  # Wait for contract to be saved

PENDING_RESPONSE=$(curl -s -b staff_cookies.txt "${BACKEND_URL}/staff/contracts/pending")
echo "$PENDING_RESPONSE" | python -m json.tool 2>/dev/null | head -20

# Step 5: Approve Contract
echo ""
echo "✅ Step 5: Approving contract and sending to SignWell..."

if [ -z "$CONTRACT_ID" ]; then
  echo "❌ No contract ID found!"
  exit 1
fi

APPROVAL_RESPONSE=$(curl -s -b staff_cookies.txt -X POST \
  "${BACKEND_URL}/staff/contracts/${CONTRACT_ID}/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "recipients": [
      {
        "email": "john.doe@example.com",
        "name": "John Doe",
        "role": "signer"
      }
    ]
  }')

echo "$APPROVAL_RESPONSE" | python -m json.tool 2>/dev/null

if echo "$APPROVAL_RESPONSE" | grep -q "signWellDocumentId"; then
  echo ""
  echo "=========================================="
  echo "🎉 TEST COMPLETED SUCCESSFULLY!"
  echo "=========================================="
  echo ""
  SIGNWELL_DOC_ID=$(echo "$APPROVAL_RESPONSE" | grep -o '"signWellDocumentId":"[^"]*"' | cut -d'"' -f4)
  echo "📋 Contract sent to SignWell!"
  echo "📋 SignWell Document ID: $SIGNWELL_DOC_ID"
  echo "✅ All systems working correctly!"
else
  echo ""
  echo "❌ Failed to send to SignWell"
  echo "Response: $APPROVAL_RESPONSE"
fi

# Cleanup
rm -f client_cookies.txt staff_cookies.txt

echo ""
echo "Test completed!"
