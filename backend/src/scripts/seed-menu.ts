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

  // ── I. Hors D'oeuvres ─────────────────────────────────────────────────

  {
    name: "Hors D'oeuvres - Chicken",
    sort_order: 1,
    items: [
      { name: 'Maple Bacon Chicken Pops',                  unit_price: 3.50, price_type: 'per_person' },
      { name: 'Chicken Tikka Skewers',                     unit_price: 3.50, price_type: 'per_person' },
      { name: 'Adobo Lime Chicken Bites',                  unit_price: 3.50, price_type: 'per_person' },
      { name: 'Chicken Satay',                             unit_price: 3.50, price_type: 'per_person' },
      { name: 'Chicken Banh Mi Slider w/ Jalapeno Slaw',  unit_price: 3.50, price_type: 'per_person' },
      { name: 'BBQ Chicken Slider',                        unit_price: 3.50, price_type: 'per_person' },
    ],
  },
  {
    name: "Hors D'oeuvres - Pork",
    sort_order: 2,
    items: [
      { name: 'Smoked Pork Belly Dippers',    unit_price: 3.50, price_type: 'per_person' },
      { name: 'Bacon Bourbon Meatballs',      unit_price: 3.50, price_type: 'per_person' },
      { name: 'Pulled Pork Sliders',          unit_price: 3.50, price_type: 'per_person' },
      { name: 'Chorizo Stuffed Baby Peppers', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Twice Baked Potato Bites',     unit_price: 3.50, price_type: 'per_person' },
    ],
  },
  {
    name: "Hors D'oeuvres - Beef",
    sort_order: 3,
    items: [
      { name: 'Asian Roast Beef Crostini w/ Wasabi Aioli',  unit_price: 3.50, price_type: 'per_person' },
      { name: 'Adobo Steak Skewers',                        unit_price: 3.50, price_type: 'per_person' },
      { name: 'Meatballs (BBQ, Swedish, Sweet and Sour)',   unit_price: 3.50, price_type: 'per_person' },
      { name: 'Mexican Stuffed Peppers w/ Cojito Cheese',   unit_price: 3.50, price_type: 'per_person' },
      { name: 'Filet Tip Crostini',                         unit_price: 4.50, price_type: 'per_person', tags: ['premium'], is_upsell: true },
    ],
  },
  {
    name: "Hors D'oeuvres - Seafood",
    sort_order: 4,
    items: [
      { name: 'Grilled Shrimp Cocktail',    unit_price: 4.75, price_type: 'per_person' },
      { name: 'Crab Stuffed Cucumbers',     unit_price: 3.50, price_type: 'per_person' },
      { name: 'South West Shrimp Crostini', unit_price: 3.50, price_type: 'per_person' },
      { name: 'Shrimp and Mango Bites',     unit_price: 3.50, price_type: 'per_person' },
      { name: 'Firecracker Shrimp',         unit_price: 4.75, price_type: 'per_person' },
      { name: 'Crab Cakes',                 unit_price: 4.75, price_type: 'per_person' },
      { name: 'Crab Dip',                   unit_price: 3.75, price_type: 'per_person' },
      { name: 'Ahi Tuna Bites',             unit_price: 3.50, price_type: 'per_person' },
    ],
  },
  {
    name: "Hors D'oeuvres - Canapes",
    sort_order: 5,
    items: [
      { name: 'Smoked Salmon Phyllo Cups',  unit_price: 3.80, price_type: 'per_person' },
      { name: 'Tropical Cucumber Cups',     unit_price: 2.00, price_type: 'per_person' },
      { name: 'Deviled Egg',                unit_price: 3.00, price_type: 'per_person' },
      { name: 'Caviar Egg',                 unit_price: 3.50, price_type: 'per_person', tags: ['premium'], is_upsell: true },
      { name: 'Caviar and Cream Crisp',     unit_price: 4.00, price_type: 'per_person', tags: ['premium'], is_upsell: true },
      { name: 'Charred Tomato and Pesto',   unit_price: 2.75, price_type: 'per_person', tags: ['vegetarian'] },
    ],
  },
  {
    name: "Hors D'oeuvres - Vegetarian",
    sort_order: 6,
    items: [
      { name: 'Bruschetta',                         unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Hummus and Pita',                    unit_price: 1.95, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Chips and Salsa',                    unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
      { name: 'Chips & Guacamole',                  unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
      { name: 'White Bean Tapenade w/ Crostini',    unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Artichoke Tapenade w/ Crostini',     unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Caprese Skewers',                    unit_price: 2.75, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Parmesan Artichoke Dip',             unit_price: 3.00, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Spanakopita',                        unit_price: 3.25, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Soft Pretzel Bites w/ Beer Cheese',  unit_price: 3.25, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Mac & Cheese Shooters',              unit_price: 3.25, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Brie Bites',                         unit_price: 3.00, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Double Stuffed Mushrooms',           unit_price: 2.75, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Gazpacho Shooters',                  unit_price: 2.25, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
    ],
  },

  // ── II. Platters ──────────────────────────────────────────────────────

  {
    name: 'Platters',
    sort_order: 7,
    items: [
      { name: 'Vegetable Platter',          unit_price: 2.25, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
      { name: 'Fruit Platter',              unit_price: 2.50, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
      { name: 'Assorted Finger Sandwiches', unit_price: 4.00, price_type: 'per_person' },
      { name: 'Cheese Platter',             unit_price: 3.50, price_type: 'per_person', tags: ['vegetarian'] },
      { name: 'Antipasto Platter',          unit_price: 3.35, price_type: 'per_person' },
      { name: 'Charcuterie Boards',         unit_price: 4.25, price_type: 'per_person' },
    ],
  },

  // ── III. Main Menus ───────────────────────────────────────────────────

  {
    name: 'Signature Combinations',
    sort_order: 5,
    items: [
      {
        name: 'Prime Rib & Salmon',
        description: 'Carved Prime Rib w/ Horseradish Cream & Au Jus, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, Glazed Carrots, Grilled Asparagus, Dinner Rolls.',
        unit_price: 39.99, price_type: 'per_person', tags: ['premium'], is_upsell: true,
      },
      {
        name: 'Chicken & Ham',
        description: 'Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls.',
        unit_price: 27.99, price_type: 'per_person',
      },
      {
        name: 'Chicken Piccata',
        description: 'Chicken Piccata, Red Wine Braised Beef Roast, Vegetable Farfalle, Long Grain Buttered Rice, Roasted Mixed Veggies, Green Beans, Dinner Rolls.',
        unit_price: 29.49, price_type: 'per_person',
      },
    ],
  },
  {
    name: 'BBQ Menus',
    sort_order: 9,
    items: [
      {
        name: 'Beef Brisket & Chicken',
        description: 'BBQ Beef Brisket (sliced), Beer Can Chicken. Includes Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad.',
        unit_price: 25.99, price_type: 'per_person',
      },
      {
        name: 'Pork & Chicken',
        description: 'Pulled BBQ Pork, Pulled BBQ Chicken. Includes Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad.',
        unit_price: 23.99, price_type: 'per_person',
      },
    ],
  },
  {
    name: 'Tasty & Casual',
    sort_order: 10,
    items: [
      {
        name: 'Burger Bar',
        description: 'Burgers (handmade) w/ Brioche Buns, Beer Can Chicken Breast. Toppings Bar: Mushrooms, Grilled Onions, Pickled Red Onion, Pickles, Lettuce, Tomato, Bacon, Assorted Sauces and Cheeses. Sides: Mac & Cheese, Roasted Red Potato (Herb and Balsamic), Seasonal Spring Greens Salad (Choice of 2 Dressings), Caprese Platter (Sliced Tomato, Fresh Mozzarella, Basil, Balsamic Glaze), Watermelon Salad (Mint, Lime Juice).',
        unit_price: 23.99, price_type: 'per_person',
      },
      {
        name: 'Southern Comfort',
        description: 'Garden Salad, Crispy Fried Chicken, Smoked Sausage, Mac and Cheese, Mashed Potatoes, Southern Style Green Beans, Buttered Corn Kernel, Corn Bread w/ Butter.',
        unit_price: 27.95, price_type: 'per_person',
      },
    ],
  },
  {
    name: 'Global Inspirations',
    sort_order: 11,
    items: [
      {
        name: 'Mexican Char Grilled',
        description: 'Carne Asada, Chili Lime Chicken, Spanish Rice, Bandito Black Beans, Peppers & Onions, Pico De Gallo, Sour Cream, Tortilla Shells.',
        unit_price: 27.99, price_type: 'per_person',
      },
      {
        name: 'Fiesta Taco Bar',
        description: 'Braised Spanish Beef, Braised Chili Chicken, Pinto Beans, Cilantro Lime Rice, Full Toppings Bar.',
        unit_price: 23.99, price_type: 'per_person',
      },
      {
        name: 'Mediterranean Bar',
        description: 'Hummus Bar (all homemade): Roasted Garlic, Sundried Tomato, Original. Toppings: Ground Lamb (hot), Grilled Mediterranean Chicken (hot), Roasted Vegetables (hot), Feta Cheese, Roasted Chickpeas, Olives, Fresh Diced Tomato, Pickled Onions, Caramelized Onions, Shredded Lettuce, Pita Bread.',
        unit_price: 23.49, price_type: 'per_person',
      },
      {
        name: 'Souvlaki Bar',
        description: 'Proteins: Chicken Souvlaki, Pork Souvlaki. Sides/Toppings: Roasted Greek Potatoes, Roasted Mixed Vegetables, Green Beans, Pita Bread, Fresh Diced Tomatoes, Diced Onions, Shredded Lettuce, Tzatziki, Feta Cheese, Fresh Cilantro.',
        unit_price: 21.49, price_type: 'per_person',
      },
      {
        name: 'Marsala Menu',
        description: 'Chicken Marsala, Roasted Cod in Peperonata Sauce, Vegetable Farfalle, Fettuccini, Roasted Mixed Veggies, Green Beans, Dinner Rolls.',
        unit_price: 25.99, price_type: 'per_person',
      },
      {
        name: 'Ravioli Menu',
        description: 'Garden Salad, Grilled Chicken with Wild Mushroom Beurre Blanc, Roasted Salmon w/ Lemon Butter Sauce, Truffle Ravioli, Wild Rice, Sauteed Zucchini and Tomatoes, Roasted Asparagus, Dinner Rolls.',
        unit_price: 31.99, price_type: 'per_person',
      },
      {
        name: 'Grilled Pasta Menu',
        description: 'Caesar Salad w/ Croutons on side, Grilled Chicken Breast, Sliced Italian Sausage, Pesto Penne Alfredo, Green Beans, Honey Glazed Carrots, Dinner Rolls.',
        unit_price: 21.49, price_type: 'per_person',
      },
    ],
  },
  {
    name: 'Soup / Salad / Sandwich',
    sort_order: 12,
    items: [
      {
        name: 'Soup / Salad / Sandwich Menu',
        description: 'Soup (Pick 2): Broccoli Cheddar, Loaded Potato, Tomato Basil Bisque, Chicken Tortilla, Vegetable Minestrone, Clam Chowder, French Onion, Chicken Noodle, Traditional Chili, Chicken Chili. Salad (Pick 2): Caesar Salad, Cobb Salad, Greek Salad, Southwest Salad, Potato Salad, Coleslaw, Seasonal Greens Salad, Bacon and Blue Cheese Salad, Pasta Salad, Sweet Kale Salad w/ Bacon and Cranberries, Design Your Own. Sandwich/Wrap (Pick 2): Gourmet Grilled Cheese, Corned Beef Reuben, Pulled Pork Cuban, Avocado BLT, Pesto Chicken, Turkey Club, Roasted Vegetable and Hummus Wrap, Philly Cheese Steak, Build Your Own.',
        unit_price: 21.95, price_type: 'per_person',
      },
    ],
  },

  // ── IV. Desserts & Coffee ─────────────────────────────────────────────

  {
    name: 'Mini Desserts - Select 4',
    sort_order: 13,
    items: [
      { name: 'Flavored Mousse Cup',        description: 'Available flavors: Chocolate, White Chocolate, Raspberry, Kahlua.',   unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: 'Lemon Bars',                 unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: 'Blondies',                   unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: '7-Layer Bars',               unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: 'Brownies',                   unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: 'Chocolate Chip Cookie Bars', unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: 'Mini Assorted Cheesecakes',  unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
      { name: 'Fruit Tarts',                description: 'Available flavors: Raspberry, Strawberry, Blackberry, Lemon, Lime.',   unit_price: 5.25, price_type: 'per_person', tags: ['dessert', 'select-4'] },
    ],
  },

  // ── III. Sweets & Wedding Cakes ────────────────────────────────────────

  {
    name: 'Coffee & Bar',
    sort_order: 14,
    items: [
      {
        name: 'Coffee Bar',
        description: 'Brewed In House Dunkin Donuts Coffee served with Sugar, Half & Half, Flavor Shots (Caramel, Hazelnut, French Vanilla). Set out with dessert.',
        unit_price: 2.75, price_type: 'per_person',
      },
      {
        name: 'Barback Package',
        description: 'Diet Coke, Coke, Sprite, Ginger Ale, Club Soda, Tonic Water, Bitters, OJ, Cranberry and Pineapple Juices, Lemons, Limes and Oranges, Cherries, Ice, Clear Plastic Cups, Coolers.',
        unit_price: 8.50, price_type: 'per_person', tags: ['bar'],
      },
      {
        name: 'Ice & Cooler Package',
        description: 'Ice (2 lbs per person @ $0.70/lb), Coolers included, Cups ($0.35 each).',
        unit_price: 1.75, price_type: 'per_person', tags: ['bar'],
      },
      {
        name: 'Cupcakes',
        description: 'Custom colors and flavors available.',
        unit_price: 3.50,
        price_type: 'per_unit',
        tags: ['wedding'],
      },
    ],
  },

  // ── V. Wedding Cakes ──────────────────────────────────────────────────

  {
    name: 'Wedding/Tiered Cakes',
    sort_order: 15,
    items: [
      {
        name: '2 Tier 6" & 8" (Serves 25)',
        description: 'Starts at $275. Cake Flavors: Yellow, White, Almond, Chocolate, Carrot, Red Velvet, Bananas Foster, Whiskey Caramel, Lemon, Spice, Funfetti, Pumpkin Spice, Cookies and Cream, Strawberry, Coconut. Fillings: Butter Cream, Lemon Curd, Raspberry Jam, Strawberry Jam, Cream Cheese Icing, Peanut Butter Cream, Mocha Buttercream, Salted Caramel Buttercream, Cinnamon Butter Cream. Buttercreams: Signature, Chocolate, Cream Cheese Frosting. For Additional Sizing, please send an inquiry.',
        unit_price: 275.00, price_type: 'flat', tags: ['wedding'],
      },
      {
        name: 'Cupcakes',
        description: 'Choice of two flavors. Custom colors available.',
        unit_price: 3.50, price_type: 'per_unit', tags: ['wedding'],
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

      const category = await prisma.menu_categories.create({
        data: {
          name: categoryData.name,
          sort_order: categoryData.sort_order,
          active: true,
        },
      });
      categoriesCreated++;

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
    { name: 'Bronze Package',          description: 'Perfect for intimate gatherings (20-50 guests)',         category: 'Standard', base_price: 20.00, price_type: 'per_person' as const, priority: 1 },
    { name: 'Silver Package',          description: 'Great for medium events (50-100 guests)',                category: 'Standard', base_price: 25.00, price_type: 'per_person' as const, priority: 2 },
    { name: 'Gold Package',            description: 'Premium experience (100-200 guests)',                    category: 'Premium',  base_price: 35.00, price_type: 'per_person' as const, priority: 3 },
    { name: 'Platinum Package',        description: 'Luxury catering for special occasions',                  category: 'Premium',  base_price: 50.00, price_type: 'per_person' as const, priority: 4 },
    { name: 'Wedding Package - Basic', description: 'Essential wedding catering',                             category: 'Wedding',  base_price: 45.00, price_type: 'per_person' as const, priority: 5 },
    { name: 'Wedding Package - Deluxe',description: 'Complete wedding catering with all services',            category: 'Wedding',  base_price: 65.00, price_type: 'per_person' as const, priority: 6 },
  ];

  let packagesCreated = 0;

  for (const pkg of packages) {
    try {
      await prisma.pricing_packages.create({ data: { ...pkg, active: true, currency: 'USD' } });
      packagesCreated++;
      console.log(`  Created: ${pkg.name}`);
    } catch (error) {
      console.error(`  Error creating "${pkg.name}":`, (error as Error).message);
    }
  }

  console.log(`\nCreated ${packagesCreated}/${packages.length} pricing packages\n`);
}

function parseDescriptionIntoDishNames(description: string): string[] {
  // Descriptions are comma-separated lists like:
  //   "Carved Prime Rib w/ Horseradish Cream & Au Jus, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, ..."
  // Some also embed sub-sections separated by periods:
  //   "Proteins: Chicken Souvlaki, Pork Souvlaki. Sides/Toppings: Roasted Greek Potatoes, ..."
  // We split on commas + periods, strip leading "Proteins:" / "Sides:" / "Toppings:" / "(Pick N)" prefixes,
  // drop empty fragments, and cap name length to keep the dishes table sane.
  return description
    .split(/[.,]/)
    .map((chunk) => chunk.trim())
    .map((chunk) => chunk.replace(/^(Proteins?|Sides?\/Toppings?|Sides?|Toppings?|Sandwich\/Wrap|Soup|Salad|Sandwich|Includes|Dessert|Fillings?|Buttercreams?|Cake Flavors?|Available flavors?|Toppings Bar|Full Toppings Bar)\s*[:(]/i, ''))
    .map((chunk) => chunk.replace(/\(Pick \d+\)/gi, ''))
    .map((chunk) => chunk.replace(/\s*\(.*?\)\s*/g, ' ').trim())
    .map((chunk) => chunk.replace(/^[-–—]\s*/, ''))
    .filter((chunk) => chunk.length > 1 && chunk.length < 120);
}

async function seedDishes() {
  console.log('\nSeeding dishes from menu_items descriptions...\n');

  const itemsWithDescriptions = await prisma.menu_items.findMany({
    where: { description: { not: null } },
    select: { id: true, name: true, description: true },
  });

  let dishesCreated = 0;
  let linksCreated = 0;
  let skipped = 0;

  for (const item of itemsWithDescriptions) {
    if (!item.description) continue;

    const dishNames = parseDescriptionIntoDishNames(item.description);
    if (dishNames.length === 0) {
      skipped++;
      continue;
    }

    for (let i = 0; i < dishNames.length; i++) {
      const dishName = dishNames[i];
      try {
        const dish = await prisma.dishes.upsert({
          where: { name: dishName },
          create: { name: dishName },
          update: {},
        });
        dishesCreated++;

        await prisma.menu_item_dishes
          .upsert({
            where: {
              menu_item_id_dish_id: { menu_item_id: item.id, dish_id: dish.id },
            },
            create: { menu_item_id: item.id, dish_id: dish.id, sort_order: i },
            update: { sort_order: i },
          })
          .then(() => linksCreated++)
          .catch(() => {});
      } catch (error) {
        console.error(`  Error upserting dish "${dishName}":`, (error as Error).message);
      }
    }
  }

  console.log('='.repeat(50));
  console.log(`Dishes upserted: ${dishesCreated}`);
  console.log(`Menu-item ↔ dish links: ${linksCreated}`);
  console.log(`Items with no parseable description: ${skipped}`);
  console.log('='.repeat(50));
}

async function main() {
  try {
    console.log('FlashBack Catering - Menu & Pricing Seeder\n');

    const existingCategories = await prisma.menu_categories.count();
    const existingItems = await prisma.menu_items.count();

    if (existingCategories > 0 || existingItems > 0) {
      console.log(`Warning: Database already has ${existingCategories} categories and ${existingItems} menu items.`);
      console.log('This will add more data. To start fresh, clear the tables first.');
      console.log('Press Ctrl+C to cancel or wait 5 seconds to continue...\n');
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }

    await seedMenu();
    await seedPricingPackages();
    await seedDishes();

    console.log('='.repeat(50));
    console.log('Seeding completed successfully!');
    console.log('='.repeat(50));

    const totalCategories = await prisma.menu_categories.count();
    const totalItems = await prisma.menu_items.count();
    const totalPackages = await prisma.pricing_packages.count();
    const totalDishes = await prisma.dishes.count();
    const totalLinks = await prisma.menu_item_dishes.count();

    console.log(`\nDatabase totals:`);
    console.log(`   Menu Categories: ${totalCategories}`);
    console.log(`   Menu Items: ${totalItems}`);
    console.log(`   Pricing Packages: ${totalPackages}`);
    console.log(`   Dishes: ${totalDishes}`);
    console.log(`   Menu-item ↔ dish links: ${totalLinks}\n`);

  } catch (error) {
    console.error('Seeding failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main();
