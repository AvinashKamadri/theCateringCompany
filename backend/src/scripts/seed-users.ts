import { PrismaClient } from '@prisma/client';
import * as argon2 from 'argon2';

const prisma = new PrismaClient();

// Sample data for generating users
const firstNames = [
  'James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
  'William', 'Barbara', 'David', 'Elizabeth', 'Richard', 'Susan', 'Joseph', 'Jessica',
  'Thomas', 'Sarah', 'Charles', 'Karen', 'Christopher', 'Nancy', 'Daniel', 'Lisa',
  'Matthew', 'Betty', 'Anthony', 'Margaret', 'Mark', 'Sandra', 'Donald', 'Ashley',
  'Steven', 'Kimberly', 'Paul', 'Emily', 'Andrew', 'Donna', 'Joshua', 'Michelle',
  'Kenneth', 'Carol', 'Kevin', 'Amanda', 'Brian', 'Dorothy', 'George', 'Melissa',
  'Timot  hy', 'Deborah', 'Ronald', 'Stephanie', 'Edward', 'Rebecca', 'Jason', 'Sharon',
  'Jeffrey', 'Laura', 'Ryan', 'Cynthia', 'Jacob', 'Kathleen', 'Gary', 'Amy',
  'Nicholas', 'Angela', 'Eric', 'Shirley', 'Jonathan', 'Anna', 'Stephen', 'Brenda',
  'Larry', 'Pamela', 'Justin', 'Emma', 'Scott', 'Nicole', 'Brandon', 'Helen',
  'Benjamin', 'Samantha', 'Samuel', 'Katherine', 'Raymond', 'Christine', 'Gregory', 'Debra',
  'Alexander', 'Rachel', 'Patrick', 'Carolyn', 'Frank', 'Janet', 'Jack', 'Catherine',
  'Dennis', 'Maria', 'Jerry', 'Heather',
];

const lastNames = [
  'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
  'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas',
  'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White',
  'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young',
  'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill', 'Flores',
  'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell', 'Mitchell',
  'Carter', 'Roberts', 'Gomez', 'Phillips', 'Evans', 'Turner', 'Diaz', 'Parker',
  'Cruz', 'Edwards', 'Collins', 'Reyes', 'Stewart', 'Morris', 'Morales', 'Murphy',
  'Cook', 'Rogers', 'Gutierrez', 'Ortiz', 'Morgan', 'Cooper', 'Peterson', 'Bailey',
  'Reed', 'Kelly', 'Howard', 'Ramos', 'Kim', 'Cox', 'Ward', 'Richardson',
  'Watson', 'Brooks', 'Chavez', 'Wood', 'James', 'Bennett', 'Gray', 'Mendoza',
  'Ruiz', 'Hughes', 'Price', 'Alvarez', 'Castillo', 'Sanders', 'Patel', 'Myers',
];

const emailDomains = [
  'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com',
  'protonmail.com', 'aol.com', 'mail.com', 'zoho.com', 'tutanota.com',
];

function generatePhone(): string {
  const areaCode = Math.floor(Math.random() * 900) + 100;
  const prefix = Math.floor(Math.random() * 900) + 100;
  const lineNumber = Math.floor(Math.random() * 9000) + 1000;
  return `+1 (${areaCode}) ${prefix}-${lineNumber}`;
}

function getRandomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

async function seedUsers() {
  console.log('🌱 Starting user seeding...\n');

  // Default password for all test users
  const defaultPassword = 'TestPass123';
  const passwordHash = await argon2.hash(defaultPassword);

  let staffCreated = 0;
  let hostsCreated = 0;
  let errors = 0;

  // Create 20 staff users
  console.log('Creating 20 staff users...');
  for (let i = 0; i < 20; i++) {
    try {
      const firstName = getRandomElement(firstNames);
      const lastName = getRandomElement(lastNames);
      const email = `${firstName.toLowerCase()}.${lastName.toLowerCase()}.${i}@catering-company.com`;
      const phone = generatePhone();

      const user = await prisma.$transaction(async (tx) => {
        const newUser = await tx.users.create({
          data: {
            email,
            password_hash: passwordHash,
            primary_phone: phone,
            status: 'active',
          },
        });

        await tx.user_profiles.create({
          data: {
            user_id: newUser.id,
            profile_type: 'staff',
            metadata: {
              first_name: firstName,
              last_name: lastName,
            },
          },
        });

        await tx.user_roles.create({
          data: {
            user_id: newUser.id,
            role_id: 'staff',
            scope_type: 'global',
            scope_id: null,
          },
        });

        return newUser;
      });

      staffCreated++;
      if (staffCreated % 5 === 0) {
        process.stdout.write(`✓ ${staffCreated} staff users created\r`);
      }
    } catch (error) {
      errors++;
      console.error(`Error creating staff user ${i}:`, error.message);
    }
  }
  console.log(`\n✅ Created ${staffCreated} staff users\n`);

  // Create 80 regular host users
  console.log('Creating 80 host users...');
  for (let i = 0; i < 80; i++) {
    try {
      const firstName = getRandomElement(firstNames);
      const lastName = getRandomElement(lastNames);
      const domain = getRandomElement(emailDomains);
      const email = `${firstName.toLowerCase()}.${lastName.toLowerCase()}.${i}@${domain}`;
      const phone = generatePhone();

      const user = await prisma.$transaction(async (tx) => {
        const newUser = await tx.users.create({
          data: {
            email,
            password_hash: passwordHash,
            primary_phone: phone,
            status: 'active',
          },
        });

        await tx.user_profiles.create({
          data: {
            user_id: newUser.id,
            profile_type: 'client',
            metadata: {
              first_name: firstName,
              last_name: lastName,
            },
          },
        });

        await tx.user_roles.create({
          data: {
            user_id: newUser.id,
            role_id: 'host',
            scope_type: 'global',
            scope_id: null,
          },
        });

        return newUser;
      });

      hostsCreated++;
      if (hostsCreated % 10 === 0) {
        process.stdout.write(`✓ ${hostsCreated} host users created\r`);
      }
    } catch (error) {
      errors++;
      console.error(`Error creating host user ${i}:`, error.message);
    }
  }
  console.log(`\n✅ Created ${hostsCreated} host users\n`);

  // Summary
  console.log('━'.repeat(50));
  console.log('📊 Seeding Summary:');
  console.log('━'.repeat(50));
  console.log(`✅ Staff users:  ${staffCreated}/20`);
  console.log(`✅ Host users:   ${hostsCreated}/80`);
  console.log(`❌ Errors:       ${errors}`);
  console.log(`📧 Total users:  ${staffCreated + hostsCreated}/100`);
  console.log('━'.repeat(50));
  console.log('\n🔐 Default password for all users: TestPass123\n');

  // Sample login credentials
  console.log('📝 Sample login credentials:');
  console.log('━'.repeat(50));

  const sampleStaff = await prisma.users.findFirst({
    where: {
      email: { contains: '@catering-company.com' }
    },
    include: {
      user_profiles: true,
    },
  });

  if (sampleStaff) {
    const metadata = sampleStaff.user_profiles[0]?.metadata as any;
    console.log('Staff User:');
    console.log(`  Name: ${metadata?.first_name} ${metadata?.last_name}`);
    console.log(`  Email: ${sampleStaff.email}`);
    console.log(`  Password: TestPass123`);
    console.log('');
  }

  const sampleHost = await prisma.users.findFirst({
    where: {
      email: { not: { contains: '@catering-company.com' } }
    },
    include: {
      user_profiles: true,
    },
  });

  if (sampleHost) {
    const metadata = sampleHost.user_profiles[0]?.metadata as any;
    console.log('Host User:');
    console.log(`  Name: ${metadata?.first_name} ${metadata?.last_name}`);
    console.log(`  Email: ${sampleHost.email}`);
    console.log(`  Password: TestPass123`);
    console.log('');
  }

  console.log('━'.repeat(50));
}

async function main() {
  try {
    // Check if roles exist
    const rolesCount = await prisma.roles.count();
    if (rolesCount === 0) {
      console.error('❌ Error: No roles found in database!');
      console.log('Please run the roles seed script first:');
      console.log('  psql -U postgres -d caterDB_prod -f sql/quick_setup.sql\n');
      process.exit(1);
    }

    // Check existing users count
    const existingUsers = await prisma.users.count();
    if (existingUsers > 0) {
      console.log(`⚠️  Warning: Database already has ${existingUsers} users.`);
      console.log('Do you want to continue? This will add 100 more users.');
      console.log('Press Ctrl+C to cancel or wait 5 seconds to continue...\n');
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }

    await seedUsers();

  } catch (error) {
    console.error('❌ Seeding failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
