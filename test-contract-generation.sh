#!/bin/bash

# Test Contract Generation Script
# Bypasses the ML chat agent and directly creates a contract for testing

BACKEND_URL="http://localhost:3001/api"
CLIENT_EMAIL="testclient@example.com"
CLIENT_PASSWORD="testpass123"

echo "🚀 Starting Contract Generation Test"
echo ""

# Step 1: Create/Login regular user
echo "Step 1: Creating/logging in regular user..."
AUTH_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${CLIENT_EMAIL}\",\"password\":\"${CLIENT_PASSWORD}\"}" \
  2>&1)

# If signup fails (user exists), try login
if echo "$AUTH_RESPONSE" | grep -q "409\|already"; then
  echo "User exists, logging in instead..."
  AUTH_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${CLIENT_EMAIL}\",\"password\":\"${CLIENT_PASSWORD}\"}")
fi

# Extract token and user ID
TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4)
USER_ID=$(echo "$AUTH_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to get authentication token"
  echo "Response: $AUTH_RESPONSE"
  exit 1
fi

echo "✅ User logged in successfully"
echo "   User ID: $USER_ID"
echo ""

# Step 2: Create a project with contract via AI intake endpoint
echo "Step 2: Creating project with contract..."
CONTRACT_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/projects/ai-intake" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
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
    "venue_has_kitchen": true,
    "special_requests": "Vegetarian options needed for 20 guests. Gluten-free desserts.",
    "dietary_restrictions": ["vegetarian", "gluten-free"],
    "generate_contract": true
  }')

# Extract project and contract info
PROJECT_ID=$(echo "$CONTRACT_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
CONTRACT_ID=$(echo "$CONTRACT_RESPONSE" | grep -o '"contract":{"id":"[^"]*' | cut -d'"' -f6)
CONTRACT_STATUS=$(echo "$CONTRACT_RESPONSE" | grep -o '"status":"[^"]*' | head -2 | tail -1 | cut -d'"' -f4)

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Failed to create project"
  echo "Response: $CONTRACT_RESPONSE"
  exit 1
fi

echo "✅ Project and Contract created successfully"
echo "   Project ID: $PROJECT_ID"
echo "   Contract ID: $CONTRACT_ID"
echo "   Contract Status: $CONTRACT_STATUS"
echo ""

# Step 3: Verify contract is pending staff approval
if [ "$CONTRACT_STATUS" = "pending_staff_approval" ]; then
  echo "✅ Contract is pending staff approval!"
  echo ""
  echo "🎯 Next Steps:"
  echo "1. Login as staff: http://localhost:3002/signin"
  echo "   Email: avinashk@flashbacklabs.com"
  echo "   Password: (your staff password)"
  echo "2. Go to: http://localhost:3002/staff/contracts"
  echo "3. You should see the contract waiting for approval!"
  echo "4. Contract ID to look for: $CONTRACT_ID"
  echo ""
  echo "📊 Contract Details:"
  echo "   Title: Catering Contract - John & Sarah Smith"
  echo "   Client: John & Sarah Smith (john.sarah@example.com)"
  echo "   Event: Wedding on 2026-06-15"
  echo "   Guests: 150"
  echo "   Venue: Blue Hills House"
else
  echo "⚠️  Contract status is not 'pending_staff_approval'"
  echo "   Actual status: $CONTRACT_STATUS"
fi

echo ""
echo "Full Response:"
echo "$CONTRACT_RESPONSE" | python -m json.tool 2>/dev/null || echo "$CONTRACT_RESPONSE"
