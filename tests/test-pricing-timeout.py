#!/usr/bin/env python
"""Test pricing calculator to find timeout issue"""
import requests
import time

print("Testing pricing calculator performance...")

# Test data
test_payload = {
    "guest_count": 100,
    "event_type": "Birthday",
    "service_type": "Drop-off",
    "selected_dishes": "Burger Bar",
    "appetizers": "none",
    "desserts": "none",
    "utensils": "standard",
    "rentals": "none"
}

try:
    start = time.time()
    response = requests.post(
        "http://localhost:8000/pricing/calculate",
        json=test_payload,
        timeout=10
    )
    elapsed = time.time() - start

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Pricing calculator works!")
        print(f"   Response time: {elapsed:.2f}s")
        print(f"   Grand Total: ${data.get('grand_total', 0):,.2f}")
        print(f"   Menu Items: {len(data.get('line_items', []))}")
    else:
        print(f"❌ Error: Status {response.status_code}")
        print(response.text[:500])

except requests.exceptions.Timeout:
    print(f"❌ Timeout after 10 seconds!")
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("Now testing with Wedding data (matching user's conversation)...")

wedding_payload = {
    "guest_count": 88,
    "event_type": "Birthday",  # From screenshot
    "service_type": "Drop-off",
    "selected_dishes": "none",
    "appetizers": "none",
    "desserts": "none",
    "utensils": "none",
    "rentals": "none"
}

try:
    start = time.time()
    response = requests.post(
        "http://localhost:8000/pricing/calculate",
        json=wedding_payload,
        timeout=10
    )
    elapsed = time.time() - start

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Wedding pricing works!")
        print(f"   Response time: {elapsed:.2f}s")
        print(f"   Grand Total: ${data.get('grand_total', 0):,.2f}")
    else:
        print(f"❌ Error: Status {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")
