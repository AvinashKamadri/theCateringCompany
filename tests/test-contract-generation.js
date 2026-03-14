/**
 * Test Contract Generation Script
 * Bypasses the ML chat agent and directly creates a contract for testing
 */

const axios = require('axios');

const BACKEND_URL = 'http://localhost:3001/api';

// Test user credentials (should match your staff account)
const STAFF_EMAIL = 'avinashk@flashbacklabs.com';
const STAFF_PASSWORD = 'your-password-here';

// Regular user for contract creation
const CLIENT_EMAIL = 'testclient@example.com';
const CLIENT_PASSWORD = 'testpass123';

async function main() {
  try {
    console.log('🚀 Starting Contract Generation Test\n');

    // Step 1: Create/Login regular user
    console.log('Step 1: Creating/logging in regular user...');
    let clientAuth;
    try {
      const signupRes = await axios.post(`${BACKEND_URL}/auth/signup`, {
        email: CLIENT_EMAIL,
        password: CLIENT_PASSWORD,
      });
      clientAuth = signupRes.data;
      console.log('✅ User created successfully');
    } catch (error) {
      if (error.response?.status === 409) {
        // User exists, login instead
        const loginRes = await axios.post(`${BACKEND_URL}/auth/login`, {
          email: CLIENT_EMAIL,
          password: CLIENT_PASSWORD,
        });
        clientAuth = loginRes.data;
        console.log('✅ User logged in successfully');
      } else {
        throw error;
      }
    }

    const clientToken = clientAuth.accessToken;
    const clientUserId = clientAuth.user.id;
    console.log(`   User ID: ${clientUserId}\n`);

    // Step 2: Create a project with contract via AI intake endpoint
    console.log('Step 2: Creating project with contract...');
    const contractData = {
      // Client info
      client_name: 'John & Sarah Smith',
      contact_email: 'john.sarah@example.com',
      contact_phone: '+1-555-123-4567',

      // Event details
      event_type: 'wedding',
      event_date: '2026-06-15',
      guest_count: 150,
      service_type: 'on_site',

      // Venue info
      venue_name: 'Blue Hills House',
      venue_address: '123 Oak Street, San Francisco, CA 94102',
      venue_has_kitchen: true,

      // Additional details
      special_requests: 'Vegetarian options needed for 20 guests. Gluten-free desserts.',
      dietary_restrictions: ['vegetarian', 'gluten-free'],

      // Request contract generation
      generate_contract: true,
    };

    const projectRes = await axios.post(
      `${BACKEND_URL}/projects/ai-intake`,
      contractData,
      {
        headers: {
          Authorization: `Bearer ${clientToken}`,
        },
      }
    );

    const project = projectRes.data.project;
    const contract = projectRes.data.contract;

    console.log('✅ Project and Contract created successfully');
    console.log(`   Project ID: ${project.id}`);
    console.log(`   Contract ID: ${contract?.id}`);
    console.log(`   Contract Status: ${contract?.status}\n`);

    // Step 3: Verify contract is pending staff approval
    if (contract?.status === 'pending_staff_approval') {
      console.log('✅ Contract is pending staff approval!');
      console.log('\n🎯 Next Steps:');
      console.log('1. Login as staff: http://localhost:3002/signin');
      console.log(`   Email: ${STAFF_EMAIL}`);
      console.log('2. Go to: http://localhost:3002/staff/contracts');
      console.log('3. You should see the contract waiting for approval!');
      console.log(`4. Contract ID to look for: ${contract.id}`);
      console.log('\n📊 Contract Details:');
      console.log(`   Title: ${contract.title}`);
      console.log(`   Client: ${contractData.client_name}`);
      console.log(`   Event: ${contractData.event_type} on ${contractData.event_date}`);
      console.log(`   Guests: ${contractData.guest_count}`);
    } else {
      console.log('⚠️  Contract status is not "pending_staff_approval"');
      console.log(`   Actual status: ${contract?.status}`);
    }

  } catch (error) {
    console.error('\n❌ Error:', error.response?.data || error.message);
    if (error.response) {
      console.error('   Status:', error.response.status);
      console.error('   Data:', JSON.stringify(error.response.data, null, 2));
    }
    process.exit(1);
  }
}

main();
