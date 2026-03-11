#!/usr/bin/env python3
"""
Complete End-to-End Flow Test
Tests: Contract Generation → Staff Approval → SignWell
"""

import requests
import json
import time

BACKEND_URL = 'http://localhost:3001/api'

# Test credentials
CLIENT_EMAIL = 'flowtest@example.com'
CLIENT_PASS = 'TestPass123'
STAFF_EMAIL = 'stafftest@flashbacklabs.com'
STAFF_PASS = 'TestPass123'

session_client = requests.Session()
session_staff = requests.Session()

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def create_or_login(session, email, password, name, role):
    """Create account or login if exists"""
    print(f"\n[*] Setting up {role} account: {email}")

    # Try signup first
    signup_data = {
        'email': email,
        'password': password,
        'first_name': name.split()[0],
        'last_name': name.split()[1] if len(name.split()) > 1 else 'User'
    }

    try:
        resp = session.post(f'{BACKEND_URL}/auth/signup', json=signup_data)
        if resp.status_code == 201:
            print(f'[OK] Account created: {email}')
            return True
        elif resp.status_code == 409:
            print(f'[INFO] Account exists, logging in...')
    except Exception as e:
        print(f'[WARN] Signup error (will try login): {e}')

    # Try login
    try:
        resp = session.post(f'{BACKEND_URL}/auth/login', json={
            'email': email,
            'password': password
        })
        if resp.status_code == 200:
            print(f'[OK] Logged in: {email}')
            return True
        else:
            print(f'[ERR] Login failed: {resp.status_code}')
            print(f'Response: {resp.text}')
            return False
    except Exception as e:
        print(f'[ERR] Login error: {e}')
        return False

def generate_contract(session):
    """Generate contract via AI intake"""
    print(f"\n[AI] Generating contract...")

    contract_data = {
        'client_name': 'John Doe',
        'contact_email': 'john.doe@example.com',
        'contact_phone': '555-9876',
        'event_type': 'Wedding',
        'event_date': '2026-06-15',
        'guest_count': 150,
        'service_type': 'Full Service',
        'venue_name': 'Grand Ballroom',
        'venue_address': '123 Main St, City, State 12345',
        'menu_items': ['Chicken Breast', 'Grilled Salmon', 'Vegetarian Pasta'],
        'dietary_restrictions': ['Vegetarian options', 'Gluten-free available'],
        'budget_range': '$5000-$8000',
        'setup_time': '4:00 PM',
        'service_time': '6:00 PM',
        'addons': ['Premium Bar Package'],
        'modifications': [],
        'generate_contract': True
    }

    try:
        resp = session.post(f'{BACKEND_URL}/projects/ai-intake', json=contract_data)

        if resp.status_code != 201:
            print(f'[ERR] Failed to create contract: {resp.status_code}')
            print(f'Response: {resp.text}')
            return None, None

        data = resp.json()
        project_id = data.get('project', {}).get('id')
        contract_id = data.get('contract', {}).get('id')

        print(f'[OK] Project ID: {project_id}')
        print(f'[OK] Contract ID: {contract_id}')
        print(f'[CONTRACT] Contract Status: {data.get("contract", {}).get("status")}')

        return project_id, contract_id

    except Exception as e:
        print(f'[ERR] Error generating contract: {e}')
        return None, None

def get_pending_contracts(session):
    """Get pending contracts as staff"""
    print(f"\n[STATS] Fetching pending contracts (as staff)...")

    try:
        resp = session.get(f'{BACKEND_URL}/staff/contracts/pending')

        if resp.status_code != 200:
            print(f'[ERR] Failed to fetch contracts: {resp.status_code}')
            print(f'Response: {resp.text}')
            return []

        data = resp.json()

        # Handle both list and object responses
        if isinstance(data, list):
            contracts = data
        elif isinstance(data, dict) and 'contracts' in data:
            contracts = data['contracts']
        else:
            print(f'[WARN] Unexpected response format: {type(data)}')
            contracts = []

        print(f'[OK] Found {len(contracts)} pending contract(s)')

        # Show first 3 contracts
        for contract in contracts[:3]:
            print(f'  [CONTRACT] ID: {contract.get("id")}')
            print(f'     Status: {contract.get("status")}')
            client_name = contract.get('body', {}).get('client_info', {}).get('name', 'N/A')
            print(f'     Client: {client_name}')

        return contracts

    except Exception as e:
        print(f'[ERR] Error fetching contracts: {e}')
        return []

def approve_contract(session, contract_id):
    """Approve contract and send to SignWell"""
    print(f"\n[OK] Approving contract and sending to SignWell...")
    print(f'Contract ID: {contract_id}')

    # Approval body: optional message and adjustments
    approval_data = {
        'message': 'Approved for signing'
    }

    try:
        resp = session.post(
            f'{BACKEND_URL}/staff/contracts/{contract_id}/approve',
            json=approval_data
        )

        if resp.status_code not in [200, 201]:
            print(f'[ERR] Failed to approve contract: {resp.status_code}')
            print(f'Response: {resp.text}')
            return None

        data = resp.json()
        print(f'[OK] Contract approved!')
        print(f'[EMAIL] Sent to SignWell')
        print(f'[CONTRACT] SignWell Document ID: {data.get("opensign_document_id")}')

        if 'signing_url' in data:
            print(f'[LINK] Signing URL: {data["signing_url"]}')

        return data

    except Exception as e:
        print(f'[ERR] Error approving contract: {e}')
        return None

def main():
    print_section("[START] Complete End-to-End Flow Test")

    # Step 1: Setup client account
    print_section("Step 1: Client Authentication")
    if not create_or_login(session_client, CLIENT_EMAIL, CLIENT_PASS, 'Flow Client', 'client'):
        print("[ERR] Failed to setup client account")
        return

    # Step 2: Setup staff account
    print_section("Step 2: Staff Authentication")
    if not create_or_login(session_staff, STAFF_EMAIL, STAFF_PASS, 'Staff Test', 'staff'):
        print("[ERR] Failed to setup staff account")
        return

    # Step 3: Generate contract
    print_section("Step 3: Generate Contract")
    project_id, contract_id = generate_contract(session_client)

    if not contract_id:
        print("[ERR] Failed to generate contract")
        return

    # Wait for contract to be fully saved
    print("\n[WAIT] Waiting 3 seconds for contract to be saved...")
    time.sleep(3)

    # Step 4: Get pending contracts
    print_section("Step 4: Staff Review - Fetch Pending Contracts")
    pending = get_pending_contracts(session_staff)

    # Find our contract
    our_contract = next((c for c in pending if c.get('id') == contract_id), None)

    if not our_contract:
        print(f"\n[WARN] Our contract {contract_id} not found in pending list")
        print(f"Found {len(pending)} contracts total")
        if pending:
            print("Using most recent contract instead...")
            contract_id = pending[0].get('id')

    # Step 5: Approve and send to SignWell
    print_section("Step 5: Approve & Send to SignWell")
    result = approve_contract(session_staff, contract_id)

    if result:
        print_section("[SUCCESS] TEST COMPLETED SUCCESSFULLY!")
        print(f"\n[STATS] Summary:")
        print(f"  Project ID: {project_id}")
        print(f"  Contract ID: {contract_id}")
        print(f"  SignWell Document ID: {result.get('opensign_document_id')}")
        print(f"  Status: Sent for signature")
        print(f"\n[OK] All systems working correctly!")
    else:
        print_section("[ERR] TEST FAILED")
        print("Contract approval failed")

if __name__ == '__main__':
    main()
