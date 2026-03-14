#!/bin/bash

echo "🤖 Testing ML Agent Contract Generation Flow"
echo "=============================================="
echo ""

ML_URL="http://localhost:8000"
THREAD_ID=""

# Function to send message and extract response
send_message() {
    local message="$1"
    echo "👤 User: $message"

    RESPONSE=$(curl -s -X POST "${ML_URL}/chat" \
      -H "Content-Type: application/json" \
      -d "{
        \"thread_id\": \"${THREAD_ID}\",
        \"message\": \"${message}\",
        \"author_id\": \"test-user-123\"
      }")

    # Extract thread_id on first message
    if [ -z "$THREAD_ID" ]; then
        THREAD_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('thread_id', ''))")
        echo "📝 Thread ID: $THREAD_ID"
    fi

    # Extract and display agent response
    AGENT_MSG=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)
    echo "🤖 Agent: $AGENT_MSG"

    # Check if complete
    IS_COMPLETE=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('is_complete', False))" 2>/dev/null)
    SLOTS_FILLED=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('slots_filled', 0))" 2>/dev/null)
    TOTAL_SLOTS=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('total_slots', 0))" 2>/dev/null)

    echo "📊 Progress: $SLOTS_FILLED/$TOTAL_SLOTS slots filled"
    echo ""

    if [ "$IS_COMPLETE" = "True" ]; then
        echo "✅ Conversation complete! Contract generated."
        echo ""
        echo "Contract Data:"
        echo "$RESPONSE" | python -m json.tool 2>/dev/null | grep -A 50 '"contract_data"'
        return 0
    fi

    sleep 1
    return 1
}

# Simulate complete conversation
send_message "Hi, I need catering for my wedding"
send_message "Syed Ayaan"
send_message "syed.ayaan@example.com"
send_message "+1-555-999-8877"
send_message "April 21, 2026"
send_message "Wedding"
send_message "The Pearl Continental, Planarcadia"
send_message "88"
send_message "Drop-off"
send_message "We need halal certified meat. Please label non-halal items clearly."
send_message "Prime Rib and Salmon, Pork and Chicken, Burger Bar"
send_message "Antipasto Platter, Cheese Platter, Bruschetta"
send_message "Wedding cake, Coffee bar"
send_message "Eco-friendly utensil package"
send_message "No"
send_message "Yes, please generate the contract"

echo ""
echo "=============================================="
echo "Test Complete!"
echo ""
echo "To view the contract in database:"
echo "PGPASSWORD='Avinash@1617' psql -U avinash -h localhost -d caterDB_prod -c \"SELECT id, status, title, body FROM contracts ORDER BY created_at DESC LIMIT 1;\""
