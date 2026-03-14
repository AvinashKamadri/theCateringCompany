#!/usr/bin/env node

/**
 * Complete End-to-End Flow Test
 * Tests: AI Chat → Contract Generation → Staff Approval → SignWell
 */

const BACKEND_URL = 'http://localhost:3001/api';
const ML_AGENT_URL = 'http://localhost:8000';

// Test data
const CLIENT_EMAIL = 'testclient@example.com';
const CLIENT_PASSWORD = 'Avinash@1617';
const STAFF_EMAIL = 'avinash@flashbacklabs.com';
const STAFF_PASSWORD = 'Avinash@1617';

let clientToken = null;
let staffToken = null;
let projectId = null;
let contractId = null;
let threadId = null;

// Helper to extract cookies
function getCookie(headers, cookieName) {
  const cookies = headers['set-cookie'] || [];
  for (const cookie of cookies) {
    if (cookie.startsWith(cookieName)) {
      return cookie.split(';')[0].split('=')[1];
    }
  }
  return null;
}

// Step 1: Create client account
async function createClientAccount() {
  console.log('\n📝 Step 1: Creating client account...');

  try {
    const response = await axios.post(`${BACKEND_URL}/auth/signup`, {
      email: CLIENT_EMAIL,
      password: CLIENT_PASSWORD,
      first_name: 'Test',
      last_name: 'Client',
      primary_phone: '555-1234'
    });

    console.log('✅ Client account created:', response.data.user.email);
    return response.headers;
  } catch (error) {
    if (error.response?.status === 400) {
      console.log('ℹ️  Client account already exists, logging in...');
      const loginRes = await axios.post(`${BACKEND_URL}/auth/login`, {
        email: CLIENT_EMAIL,
        password: CLIENT_PASSWORD
      });
      return loginRes.headers;
    }
    throw error;
  }
}

// Step 2: Create staff account
async function createStaffAccount() {
  console.log('\n📝 Step 2: Creating staff account...');

  try {
    const response = await axios.post(`${BACKEND_URL}/auth/signup`, {
      email: STAFF_EMAIL,
      password: STAFF_PASSWORD,
      first_name: 'Staff',
      last_name: 'Admin',
      primary_phone: '555-5678'
    });

    console.log('✅ Staff account created:', response.data.user.email);
    return response.headers;
  } catch (error) {
    if (error.response?.status === 400) {
      console.log('ℹ️  Staff account already exists, logging in...');
      const loginRes = await axios.post(`${BACKEND_URL}/auth/login`, {
        email: STAFF_EMAIL,
        password: STAFF_PASSWORD
      });
      return loginRes.headers;
    }
    throw error;
  }
}

// Step 3: Generate contract via AI intake
async function generateContract(headers) {
  console.log('\n🤖 Step 3: Generating contract via AI intake...');

  const contractData = {
    client_name: 'John Doe',
    contact_email: 'john.doe@example.com',
    contact_phone: '555-9876',
    event_type: 'Wedding',
    event_date: '2026-06-15',
    guest_count: 150,
    service_type: 'Full Service',
    venue_name: 'Grand Ballroom',
    venue_address: '123 Main St, City, State 12345',
    menu_items: ['Chicken Breast', 'Grilled Salmon', 'Vegetarian Pasta'],
    dietary_restrictions: ['Vegetarian options', 'Gluten-free available'],
    budget_range: '$5000-$8000',
    setup_time: '4:00 PM',
    service_time: '6:00 PM',
    addons: ['Premium Bar Package'],
    modifications: [],
    generate_contract: true
  };

  const cookie = getCookie(headers, 'app_jwt');

  const response = await axios.post(
    `${BACKEND_URL}/projects/ai-intake`,
    contractData,
    {
      headers: {
        Cookie: `app_jwt=${cookie}`
      }
    }
  );

  projectId = response.data.project.id;
  contractId = response.data.contract?.id;

  console.log('✅ Project created:', projectId);
  console.log('✅ Contract created:', contractId);
  console.log('📋 Contract status:', response.data.contract?.status);

  return response.data;
}

// Step 4: Get pending contracts (as staff)
async function getPendingContracts(headers) {
  console.log('\n📊 Step 4: Fetching pending contracts (as staff)...');

  const cookie = getCookie(headers, 'app_jwt');

  const response = await axios.get(
    `${BACKEND_URL}/staff/contracts/pending`,
    {
      headers: {
        Cookie: `app_jwt=${cookie}`
      }
    }
  );

  console.log(`✅ Found ${response.data.length} pending contract(s)`);

  if (response.data.length > 0) {
    const contract = response.data[0];
    console.log('📋 Contract ID:', contract.id);
    console.log('📋 Status:', contract.status);
    console.log('👤 Client:', contract.body?.client_info?.name);
  }

  return response.data;
}

// Step 5: Approve contract and send to SignWell
async function approveContract(headers, contractId) {
  console.log('\n✅ Step 5: Approving contract and sending to SignWell...');

  const cookie = getCookie(headers, 'app_jwt');

  try {
    const response = await axios.post(
      `${BACKEND_URL}/staff/contracts/${contractId}/approve`,
      {
        recipients: [
          {
            email: 'john.doe@example.com',
            name: 'John Doe',
            role: 'signer'
          }
        ]
      },
      {
        headers: {
          Cookie: `app_jwt=${cookie}`
        }
      }
    );

    console.log('✅ Contract approved!');
    console.log('📧 Sent to SignWell');
    console.log('📋 SignWell Document ID:', response.data.signWellDocumentId);
    console.log('🔗 Signing URL:', response.data.signingUrl);

    return response.data;
  } catch (error) {
    console.error('❌ Error approving contract:', error.response?.data || error.message);
    throw error;
  }
}

// Main test flow
async function runTest() {
  console.log('🚀 Starting Complete End-to-End Flow Test\n');
  console.log('=' .repeat(60));

  try {
    // Step 1: Create client account
    const clientHeaders = await createClientAccount();

    // Step 2: Create staff account
    const staffHeaders = await createStaffAccount();

    // Step 3: Generate contract (as client)
    const projectData = await generateContract(clientHeaders);

    if (!contractId) {
      throw new Error('Contract was not created!');
    }

    // Wait a moment for contract to be fully saved
    console.log('\n⏳ Waiting 2 seconds for contract to be saved...');
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Step 4: Get pending contracts (as staff)
    const pendingContracts = await getPendingContracts(staffHeaders);

    // Find our contract
    const ourContract = pendingContracts.find(c => c.id === contractId);

    if (!ourContract) {
      console.error('❌ Our contract not found in pending list!');
      console.log('Expected contract ID:', contractId);
      console.log('Found contracts:', pendingContracts.map(c => c.id));
      return;
    }

    // Step 5: Approve and send to SignWell
    const approvalResult = await approveContract(staffHeaders, contractId);

    console.log('\n' + '='.repeat(60));
    console.log('🎉 TEST COMPLETED SUCCESSFULLY!');
    console.log('='.repeat(60));
    console.log('\n📊 Summary:');
    console.log(`  Project ID: ${projectId}`);
    console.log(`  Contract ID: ${contractId}`);
    console.log(`  SignWell Document ID: ${approvalResult.signWellDocumentId}`);
    console.log(`  Status: Sent for signature`);
    console.log('\n✅ All systems working correctly!');

  } catch (error) {
    console.error('\n❌ TEST FAILED!');
    console.error('Error:', error.message);

    if (error.response) {
      console.error('Status:', error.response.status);
      console.error('Data:', JSON.stringify(error.response.data, null, 2));
    }

    console.error('\nStack:', error.stack);
    process.exit(1);
  }
}

// Run the test
runTest();
