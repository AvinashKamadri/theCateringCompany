import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

interface MenuItem {
  name: string; 
  description?: string;
  unit_price: number;
  price_type: 'per_person' | 'flat' | 'per_unit' | 'per_hour';
  allergens?: string[];
  tags?: string[];
  is_upsell?: boolean;
}

interface MenuCategory {
  name: string;
  sort_order: number;
  items: MenuItem[];
}

const menuData: MenuCategory[] = [
  // ── I. Hors D'oeuvres & Platters ──────────────────────────────────────

  {
    name: 'Hors D\'oeuvres - Poultry',
    sort_order: 1,
    items: [
      { name: 'Adobo Lime Chicken Skewers with Cilantro Cream', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Chicken Banh Mi Sliders with Pickled Veggies & Sriracha Aioli', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Maple Bacon Chicken Pops', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Chicken Satay with Peanut Sauce', unit_price: 3.50, price_type: 'per_person' },
    ],
  },
  {
    name: 'Hors D\'oeuvres - Meat',
    sort_order: 2,
    items: [
      { name: 'Fillet Tip Crostini with Horseradish Cream & Microgreens', unit_price: 4.50, price_type: 'per_person', tags: ['premium'], is_upsell: true },
      { name: 'Philly Cheesesteak Eggroll with Sriracha Ketchup', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Mini Beef Sliders with Caramelized Onions & Swiss', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Candied Bacon Skewers', unit_price: 3.50, price_type: 'per_person' },
    ],
  },
  {
    name: 'Hors D\'oeuvres - Seafood & Canapes',
    sort_order: 3,
    items: [
      { name: 'Coconut Shrimp with Sweet Chili Sauce', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Mini Crab Cakes with Remoulade Sauce', unit_price: 4.75, price_type: 'per_person' },
      { name: 'Shrimp Salad in Cucumber Cups', unit_price: 2.25, price_type: 'per_person' },
      { name: 'Bruschetta (Tomato, Basil, Garlic on Crostini)', unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Caprese Skewers (Tomato, Mozzarella, Basil, Balsamic Glaze)', unit_price: 2.00, price_type: 'per_person', tags: ['vegetarian'] },
    ],
  },
  {
    name: 'Platters & Displays',
    sort_order: 4,
    items: [
      { name: 'Vegetable Crudite & Hummus/Pita', description: 'Assorted fresh veggies & dip', unit_price: 2.25, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
      { name: 'Fruit Display', description: 'Seasonal sliced fruit', unit_price: 3.50, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
      { name: 'Cheese & Fruit Display', description: 'Domestic & Imported cheeses', unit_price: 4.25, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Charcuterie Board', description: 'Cured meats, cheeses, olives, and nuts', unit_price: 4.25, price_type: 'per_person' },
    ],
  },

  // ── II. Main Event Bars & Signature Combos ─────────────────────────────
  // All include high-quality disposable ware and choice of Water, Lemonade, or Iced Tea

  {
    name: 'Signature Combinations',
    sort_order: 5,
    items: [
      {
        name: 'Prime Rib & Salmon',
        description: 'Carved Prime Rib (Horseradish Cream and Au Jus), Roasted Salmon (Dill Sauce). Includes Roasted Potatoes, Wild Rice, Glazed Carrots, Roasted Asparagus, and Dinner Rolls.',
        unit_price: 39.99,
        price_type: 'per_person',
      },
      {
        name: 'Chicken Piccata',
        description: 'Lemon Caper Sauce, Penne Pasta (Marinara), Roasted Vegetables, Caesar Salad, and Garlic Bread.',
        unit_price: 29.49,
        price_type: 'per_person',
      },
      {
        name: 'Chicken & Ham',
        description: 'Grilled Chicken Breast & Mango Glazed Ham. Includes Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, and Dinner Rolls.',
        unit_price: 27.99,
        price_type: 'per_person',
      },
    ],
  },
  {
    name: 'Themed Food Bars',
    sort_order: 6,
    items: [
      {
        name: 'Southern Comfort',
        description: 'Fried Chicken, Mac & Cheese, Collard Greens, Cornbread, Biscuits, Caprese Platter, and Watermelon Salad.',
        unit_price: 27.95,
        price_type: 'per_person',
      },
      {
        name: 'Mexican Char Grilled',
        description: 'Carne Asada, Grilled Chicken, Rice/Beans, Pico, Guacamole, Tortillas, and Chips/Salsa.',
        unit_price: 27.99,
        price_type: 'per_person',
      },
      {
        name: 'BBQ Brisket & Chicken',
        description: 'Smoked Brisket, BBQ Chicken, Beans, Coleslaw, Cornbread, Mac & Cheese, and Pickles/Onions.',
        unit_price: 25.99,
        price_type: 'per_person',
      },
      {
        name: 'Mediterranean Bar',
        description: 'Chicken Shawarma, Beef Kofta, Hummus/Pita, Tabbouleh, Greek Salad, Rice Pilaf, and Tzatziki.',
        unit_price: 23.49,
        price_type: 'per_person',
      },
      {
        name: 'Burger Bar',
        description: 'Angus Beef, Grilled Chicken, All Fixings, Fries, Coleslaw, and Baked Beans.',
        unit_price: 23.99,
        price_type: 'per_person',
      },
    ],
  },
  {
    name: 'Casual & Light Fare',
    sort_order: 7,
    items: [
      {
        name: 'Soup, Salad & Sandwich',
        description: 'Assorted Sandwiches, Choice of Soup (Tomato Bisque, Chicken Noodle, or Wedding), Mixed Green Salad, Chips, and Cookies.',
        unit_price: 21.95,
        price_type: 'per_person',
      },
    ],
  },

  // ── III. Sweets & Wedding Cakes ────────────────────────────────────────

  {
    name: 'Desserts & Coffee',
    sort_order: 8,
    items: [
      {
        name: 'Mini Dessert Display',
        description: 'Select 4: Mousse Cups, Cannolis, Brownie Bites, Fruit Tarts, Mini Cupcakes, or Choc-Dipped Strawberries.',
        unit_price: 5.25,
        price_type: 'per_person',
      },
      {
        name: 'Coffee Bar',
        description: 'Dunkin\' Donuts Regular/Decaf, Hot Tea, Hot Chocolate, Syrups (Vanilla/Caramel/Hazelnut), and Creamers.',
        unit_price: 2.75,
        price_type: 'per_person',
      },
    ],
  },
  {
    name: 'Wedding Cakes (by Rachel\'s Bloomers)',
    sort_order: 9,
    items: [
      {
        name: '2-Tier Cake',
        description: '6" and 8" tiers. Serves approximately 25 guests. Includes choice of flavor and buttercream frosting.',
        unit_price: 295.00,
        price_type: 'flat',
        tags: ['wedding'],
      },
      {
        name: 'Cupcakes',
        description: 'Custom colors and flavors available.',
        unit_price: 3.60,
        price_type: 'per_unit',
        tags: ['wedding'],
      },
    ],
  },

];

async function seedMenu() {
  console.log('Starting menu seeding...\n');

  let categoriesCreated = 0;
  let itemsCreated = 0;
  let errors = 0;

  for (const categoryData of menuData) {
    try {
      console.log(`Creating category: ${categoryData.name}...`);

      // Create category
      const category = await prisma.menu_categories.create({
        data: {
          name: categoryData.name,
          sort_order: categoryData.sort_order,
          active: true,
        },
      });
      categoriesCreated++;

      // Create menu items for this category
      for (const itemData of categoryData.items) {
        try {
          await prisma.menu_items.create({
            data: {
              category_id: category.id,
              name: itemData.name,
              description: itemData.description || null,
              unit_price: itemData.unit_price,
              price_type: itemData.price_type,
              allergens: itemData.allergens || [],
              tags: itemData.tags || [],
              is_upsell: itemData.is_upsell || false,
              active: true,
              currency: 'USD',
              minimum_quantity: 1,
            },
          });
          itemsCreated++;
        } catch (error) {
          errors++;
          console.error(`  Error creating item "${itemData.name}":`, (error as Error).message);
        }
      }

      console.log(`  Created ${categoryData.items.length} items`);
    } catch (error) {
      errors++;
      console.error(`Error creating category "${categoryData.name}":`, (error as Error).message);
    }
  }

  console.log('\n' + '='.repeat(50));
  console.log('Menu Seeding Summary:');
  console.log('='.repeat(50));
  console.log(`Categories created: ${categoriesCreated}/${menuData.length}`);
  console.log(`Menu items created: ${itemsCreated}`);
  console.log(`Errors: ${errors}`);
  console.log('='.repeat(50));

  // Show sample items from each category
  console.log('\nSample Menu Items:\n');
  const categories = await prisma.menu_categories.findMany({
    include: {
      menu_items: {
        take: 2,
        orderBy: { name: 'asc' },
      },
    },
    orderBy: { sort_order: 'asc' },
    take: 5,
  });

  for (const cat of categories) {
    console.log(`${cat.name}:`);
    for (const item of cat.menu_items) {
      console.log(`  - ${item.name} - $${item.unit_price} ${item.price_type}`);
    }
    console.log('');
  }
}

async function seedPricingPackages() {
  console.log('\nCreating pricing packages...\n');

  const packages = [
    {
      name: 'Bronze Package',
      description: 'Perfect for intimate gatherings (20-50 guests)',
      category: 'Standard',
      base_price: 20.00,
      price_type: 'per_person' as const,
      priority: 1,
    },
    {
      name: 'Silver Package',
      description: 'Great for medium events (50-100 guests)',
      category: 'Standard',
      base_price: 25.00,
      price_type: 'per_person' as const,
      priority: 2,
    },
    {
      name: 'Gold Package',
      description: 'Premium experience (100-200 guests)',
      category: 'Premium',
      base_price: 35.00,
      price_type: 'per_person' as const,
      priority: 3,
    },
    {
      name: 'Platinum Package',
      description: 'Luxury catering for special occasions',
      category: 'Premium',
      base_price: 50.00,
      price_type: 'per_person' as const,
      priority: 4,
    },
    {
      name: 'Wedding Package - Basic',
      description: 'Essential wedding catering',
      category: 'Wedding',
      base_price: 45.00,
      price_type: 'per_person' as const,
      priority: 5,
    },
    {
      name: 'Wedding Package - Deluxe',
      description: 'Complete wedding catering with all services',
      category: 'Wedding',
      base_price: 65.00,
      price_type: 'per_person' as const,
      priority: 6,
    },
  ];

  let packagesCreated = 0;

  for (const pkg of packages) {
    try {
      await prisma.pricing_packages.create({
        data: {
          ...pkg,
          active: true,
          currency: 'USD',
        },
      });
      packagesCreated++;
      console.log(`  Created: ${pkg.name}`);
    } catch (error) {
      console.error(`  Error creating "${pkg.name}":`, (error as Error).message);
    }
  }

  console.log(`\nCreated ${packagesCreated}/${packages.length} pricing packages\n`);
}

async function main() {
  try {
    console.log('FlashBack Catering - Menu & Pricing Seeder\n');

    // Check existing data
    const existingCategories = await prisma.menu_categories.count();
    const existingItems = await prisma.menu_items.count();

    if (existingCategories > 0 || existingItems > 0) {
      console.log(`Warning: Database already has ${existingCategories} categories and ${existingItems} menu items.`);
      console.log('This will add more data. To start fresh, clear the tables first.');
      console.log('Press Ctrl+C to cancel or wait 5 seconds to continue...\n');
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }

    // Seed menu categories and items
    await seedMenu();

    // Seed pricing packages
    await seedPricingPackages();

    console.log('='.repeat(50));
    console.log('Seeding completed successfully!');
    console.log('='.repeat(50));

    // Final counts
    const totalCategories = await prisma.menu_categories.count();
    const totalItems = await prisma.menu_items.count();
    const totalPackages = await prisma.pricing_packages.count();

    console.log(`\nDatabase totals:`);
    console.log(`   Menu Categories: ${totalCategories}`);
    console.log(`   Menu Items: ${totalItems}`);
    console.log(`   Pricing Packages: ${totalPackages}\n`);

  } catch (error) {
    console.error('Seeding failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
