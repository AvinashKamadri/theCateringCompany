#!/usr/bin/env python
import requests
import json

ML_URL = "http://localhost:8000"
THREAD_ID = "b386b103-eb75-4986-9acd-fbedca1952e7"

print("Finishing contract generation...")
response = requests.post(
    f"{ML_URL}/chat",
    json={
        "thread_id": THREAD_ID,
        "message": "Everything looks perfect, please generate the contract",
        "author_id": "test"
    }
)

data = response.json()

print(f"Complete: {data.get('is_complete')}")
print(f"Has contract_data: {bool(data.get('contract_data'))}")
print()

if data.get('contract_data'):
    cd = data['contract_data']
    print("CONTRACT GENERATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"Contract Number: {cd.get('contract_number')}")
    print(f"Client: {cd.get('client_name')}")
    print(f"Event: {cd.get('event_type')} on {cd.get('event_date')}")
    print(f"Venue: {cd.get('venue_name')}")
    print(f"Guests: {cd.get('guest_count')}")
    print()
    billing = cd.get('billing', {})
    print("BILLING:")
    print(f"  Menu Subtotal: ${billing.get('menu_subtotal', 0):,.2f}")
    print(f"  Service Charge: ${billing.get('service_charge', 0):,.2f}")
    print(f"  Tax ({billing.get('tax', {}).get('percentage', 'N/A')}): ${billing.get('tax', {}).get('amount', 0):,.2f}")
    print(f"  Gratuity ({billing.get('gratuity', {}).get('percentage', 'N/A')}): ${billing.get('gratuity', {}).get('amount', 0):,.2f}")
    print(f"  GRAND TOTAL: ${billing.get('grand_total', 0):,.2f}")
    print()
    print(f"  Deposit (50%): ${billing.get('deposit', {}).get('amount', 0):,.2f} - {billing.get('deposit', {}).get('due', '')}")
    print(f"  Balance: ${billing.get('balance', {}).get('amount', 0):,.2f} - {billing.get('balance', {}).get('due', '')}")
    print()
    print(f"Menu Items: {len(cd.get('menu_items', []))}")
    for item in cd.get('menu_items', []):
        print(f"  - {item['name']}: ${item['unit_price']:.2f}/{item['price_type']} = ${item['total']:.2f}")

    # Save full contract to file
    with open('/tmp/generated-contract.json', 'w') as f:
        json.dump(cd, f, indent=2)
    print()
    print("Full contract saved to: /tmp/generated-contract.json")
else:
    print("Contract not generated")
    print(f"Message: {data.get('message', '')[:300]}")
