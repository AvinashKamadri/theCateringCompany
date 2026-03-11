#!/bin/bash

echo "Testing Enhanced ML Agent Contract Generation"
echo "=============================================="
echo ""

ML_URL="http://localhost:8000"
THREAD_ID=""

# Helper function to send message
send() {
    MSG="$1"
    echo "User: $MSG"

    RESPONSE=$(curl -s -X POST "${ML_URL}/chat" \
      -H "Content-Type: application/json" \
      -d "{
        \"thread_id\": \"${THREAD_ID}\",
        \"message\": \"${MSG}\",
        \"author_id\": \"test-user\"
      }")

    if [ -z "$THREAD_ID" ]; then
        THREAD_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('thread_id', ''))")
    fi

    AGENT=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)
    echo "Agent: $AGENT"
    echo ""

    sleep 1
}

# Simulate complete conversation matching sample contract
send "Hi, I need catering for my wedding"
send "Syed Ayaan"
send "April 21, 2026"
send "Wedding"
send "The Pearl Continental, Planarcadia"
send "88 guests"
send "Drop-off"

# Menu selection
send "Prime Rib and Salmon, Pork and Chicken, Burger Bar"
send "Antipasto Platter, Cheese Platter, Bruschetta, Tomato and Guacamole, Gazpacho Shooters"
send "No special menu notes"
send "Eco-friendly utensil package"
send "Wedding tiered cake, Coffee bar"
send "No rentals needed"
send "No florals needed"
send "We need halal certified meat. Please label non-halal items clearly. Pork dish can be included but must be clearly labeled."
send "Halal requirements, some vegetarian and gluten-free guests"

echo "=============================================="
echo "Contract generation complete!"
echo ""
echo "To view contract in database:"
echo "PGPASSWORD='Avinash@1617' psql -U avinash -h localhost -d caterDB_prod -c \"SELECT contract_number, client_name, grand_total FROM contracts ORDER BY created_at DESC LIMIT 1;\""
