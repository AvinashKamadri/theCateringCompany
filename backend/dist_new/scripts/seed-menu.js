"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@prisma/client");
const prisma = new client_1.PrismaClient();
const menuData = [
    {
        name: 'Hors D\'oeuvres - Beef',
        sort_order: 1,
        items: [
            { name: 'Asian Roast Beef Crostini w/ Wasabi Aioli', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Adobo Steak Skewers', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Meatballs (BBQ, Swedish, Sweet and Sour)', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Mexican Stuffed Peppers w/ Cojito Cheese', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Filet Tip Crostini', unit_price: 3.50, price_type: 'per_person', tags: ['premium'] },
        ],
    },
    {
        name: 'Hors D\'oeuvres - Chicken',
        sort_order: 2,
        items: [
            { name: 'Maple Bacon Chicken Pops', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Chicken Tikka Skewers', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Adobo Lime Chicken Bites', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Chicken Satay', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Chicken Bahn Mi Slider w/ Jalapeno Slaw', unit_price: 3.50, price_type: 'per_person' },
            { name: 'BBQ Chicken Slider', unit_price: 3.50, price_type: 'per_person' },
        ],
    },
    {
        name: 'Hors D\'oeuvres - Pork',
        sort_order: 3,
        items: [
            { name: 'Smoked Pork Belly Dippers', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Bacon Bourbon Meatballs', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Pulled Pork Sliders', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Chorizo Stuffed Baby Peppers', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Twice Baked Potato Bites', unit_price: 3.50, price_type: 'per_person' },
        ],
    },
    {
        name: 'Hors D\'oeuvres - Seafood',
        sort_order: 4,
        items: [
            { name: 'Grilled Shrimp Cocktail', unit_price: 4.75, price_type: 'per_person' },
            { name: 'Crab Stuffed Cucumbers', unit_price: 3.50, price_type: 'per_person' },
            { name: 'South West Shrimp Crostini', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Shrimp and Mango Bites', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Firecracker Shrimp', unit_price: 4.75, price_type: 'per_person' },
            { name: 'Bacon Shrimp', unit_price: 4.75, price_type: 'per_person' },
            { name: 'Crab Dip', unit_price: 3.75, price_type: 'per_person' },
            { name: 'Ahi Tuna Bites', unit_price: 3.50, price_type: 'per_person' },
        ],
    },
    {
        name: 'Hors D\'oeuvres - Vegetarian',
        sort_order: 5,
        items: [
            { name: 'Par Pardon', unit_price: 1.25, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Bruschetta', unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Tomatoes and Feta', unit_price: 1.95, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Chips and Salsa', unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
            { name: 'Tomato & Guacamole', unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
            { name: 'White Bean Tapenade w/ Crostini', unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Artichoke Tapenade w/ Crostini', unit_price: 1.75, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Caprese Skewers', unit_price: 2.75, price_type: 'per_person', tags: ['vegetarian'] },
        ],
    },
    {
        name: 'Hors D\'oeuvres - Canapes',
        sort_order: 6,
        items: [
            { name: 'Smoked Salmon Phyllo Cups', unit_price: 3.80, price_type: 'per_person' },
            { name: 'Tropical Cucumber Cups', unit_price: 2.00, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Deviled Egg', unit_price: 3.00, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Caviar Egg', unit_price: 3.50, price_type: 'per_person' },
            { name: 'Caviar and Cream Crisp', unit_price: 4.00, price_type: 'per_person' },
            { name: 'Charred Tomato and Pesto', unit_price: 2.75, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Parmesan Artichoke Dip', unit_price: 3.00, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Spanakopita', unit_price: 3.25, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Brie & Cranberry Puff Cheese', unit_price: 3.25, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Mac & Cheese Shooters', unit_price: 3.25, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Bite Bites', unit_price: 3.00, price_type: 'per_person' },
            { name: 'Double Stuffed Mushrooms', unit_price: 2.75, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Gazpacho Shooters', unit_price: 2.25, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
        ],
    },
    {
        name: 'Platters',
        sort_order: 7,
        items: [
            { name: 'Vegetable Platter', unit_price: 2.25, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
            { name: 'Fruit Platter', unit_price: 2.50, price_type: 'per_person', tags: ['vegetarian', 'vegan'] },
            { name: 'Assorted Finger Sandwiches', unit_price: 4.00, price_type: 'per_person' },
            { name: 'Cheese Platter', unit_price: 3.50, price_type: 'per_person', tags: ['vegetarian'] },
            { name: 'Antipasto Platter', unit_price: 3.35, price_type: 'per_person' },
            { name: 'Charcuterie Boards', unit_price: 4.25, price_type: 'per_person' },
        ],
    },
    {
        name: 'Signature Combinations',
        sort_order: 8,
        items: [
            {
                name: 'Prime Rib & Salmon',
                description: 'Carved Prime Rib w/ Horseradish Cream & Aju, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, Glazed Carrots, Grilled Asparagus, Dinner Rolls',
                unit_price: 39.99,
                price_type: 'per_person',
            },
            {
                name: 'Chicken & Ham',
                description: 'Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls',
                unit_price: 27.99,
                price_type: 'per_person',
            },
            {
                name: 'Chicken Piccata',
                description: 'Chicken Piccata, Red Wine Braised Beef Roast, Long Grain Buttered Rice, Vegetable Farfalle, Roasted Mixed Veggies, Green Beans, Dinner Rolls',
                unit_price: 29.49,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'BBQ Menus',
        sort_order: 9,
        items: [
            {
                name: 'Beef Brisket & Chicken',
                description: 'BBQ Beef Brisket (sliced), Beer Can Chicken. Includes: Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad',
                unit_price: 25.99,
                price_type: 'per_person',
            },
            {
                name: 'Pork & Chicken',
                description: 'Pulled BBQ Pork, Pulled BBQ Chicken. Includes: Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad',
                unit_price: 23.99,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Casual Fare - Burger Bar',
        sort_order: 10,
        items: [
            {
                name: 'Burger Bar',
                description: 'Burgers (handmade) w/ Brioche Buns, Beer Can Chicken Breast. Toppings Bar: Mushrooms, Grilled Peppers and Onion, Pickles, Lettuce, Tomato, Bacon, Assorted Sauces and Cheese, Mac & Cheese, Roasted Red Potato (Herb and Balsamic), Seasonal Spring Greens Salad - Choice of 2 Dressings',
                unit_price: 23.99,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Casual Fare - Southern Comfort',
        sort_order: 11,
        items: [
            {
                name: 'Southern Comfort',
                description: 'Garden Salad, Crispy Fried Chicken, Smoked Sausage, Mac and Cheese, Mashed Potatoes, Southern Style Green Beans, Buttered Corn Kernel, Corn Bread w/ Butter',
                unit_price: 27.95,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Mexican',
        sort_order: 12,
        items: [
            {
                name: 'Char Grilled',
                description: 'Carne Asada, Chili Lime Chicken, Spanish Rice, Bandito Black Beans, Peppers & Onions, Pico De Gallo, Sour Cream, Tortilla Shells',
                unit_price: 27.99,
                price_type: 'per_person',
            },
            {
                name: 'Fiesta Taco Bar',
                description: 'Braised Spanish Beef, Braised Chili Chicken, Pinto Beans, Cilantro Lime Rice, Full Toppings Bar',
                unit_price: 23.99,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Mediterranean Bars',
        sort_order: 13,
        items: [
            {
                name: 'Mediterranean Bar',
                description: 'Hummus Bar (all homemade), Roasted Garlic Hummus, Sundried Tomato Hummus, Original Hummus. Toppings: Grilled Marinated Chicken (hot), Roasted Vegetables (hot), Feta Cheese, Roasted Chickpeas, Olives, Fresh Diced Tomato, Pickled Onions, Caramelized Onions, Shredded Lettuce',
                unit_price: 23.49,
                price_type: 'per_person',
            },
            {
                name: 'Souvlaki Bar',
                description: 'Chicken Souvlaki, Tzatziki Sauce, Roasted Greek Potatoes, Roasted Mixed Vegetables, Green Beans, Pita Bread. Toppings: Fresh Diced Tomatoes, Diced Onions, Shredded Lettuce, Tzatziki, Feta Cheese, Fresh Cilantro',
                unit_price: 21.49,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Italian Bars',
        sort_order: 14,
        items: [
            {
                name: 'Marsala Menu',
                description: 'Chicken Marsala, Roasted Cod in Peperonata Sauce, Vegetable Farfalle, Fettuccini, Roasted Mixed Veggies, Green Beans, Dinner Rolls',
                unit_price: 25.99,
                price_type: 'per_person',
            },
            {
                name: 'Ravioli Menu',
                description: 'Garden Salad, Grilled Chicken with Wild Mushroom Buer Blanc, Roasted Salmon w/ Lemon Butter Sauce, Truffle Ravioli, Wild Rice, Sautéed Zucchini and Tomatoes, Roasted Asparagus, Dinner Rolls',
                unit_price: 31.99,
                price_type: 'per_person',
            },
            {
                name: 'Grilled Pasta Menu',
                description: 'Caesar Salad w/ Croutons on side, Grilled Chicken Breast, Sliced Italian Sausage, Pesto Penne Alfredo, Green Beans, Honey Glazed Carrots, Dinner Rolls',
                unit_price: 21.99,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Soup/Salad/Sandwich',
        sort_order: 15,
        items: [
            {
                name: 'Soup Pick 2',
                description: 'Choose from: Broccoli Cheddar, Loaded Potato, Tomato Basil Bisque, Chicken Tortilla, Vegetable Minestrone, Clam Chowder, French Onion, Chicken Noodle, Chicken Chili',
                unit_price: 21.95,
                price_type: 'per_person',
            },
            {
                name: 'Salad Pick 2',
                description: 'Choose from: Seasonal Greens Salad, Bacon and Blue Cheese Salad, Garden Salad, Southwest Salad, Pasta Salad, Potato Salad, Coleslaw, Sweet Kale salad w/ Bacon and Cranberries',
                unit_price: 21.95,
                price_type: 'per_person',
            },
            {
                name: 'Sandwich Pick 2',
                description: 'Choose from: Gourmet Grilled Cheese, Corned Beef and Reuben, Grilled Chicken, Avocado BLT, Pesto Chicken, Turkey Club, Panini Vegetable and Hummus Wrap, Philly Cheese Steaks, **Build Your Own**',
                unit_price: 21.95,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Potato Bar',
        sort_order: 16,
        items: [
            {
                name: 'Potato Bar',
                description: 'Choose Your Potato: Baked Idaho Potato, Roasted Garlic Mashed Potato, Sour Cream and Chive Mashed, Cheddar Mashed, Hash Brown Casserole. Choose 2 Proteins: Pulled Pork, Taco Meat, Smoked Brisket, BBQ Pulled Chicken, Beef Chili, Chicken Chili, Chicken Nuggets, Grilled Chicken. Choose 8 Toppings: Bacon, Sour Cream, Cheddar Cheese, Mont Jack Cheese, Roasted Peppers, Blue Cheese, Ranch Dressing, Tomatoes, Hot Sauce, Black Beans, Green Onion, Broccoli, Salsa, Black Olives, Demi-Glace Gravy, Queso. Or Make it a loaded Toppings Bar for additional $7.50',
                unit_price: 19.95,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Coffee and Desserts',
        sort_order: 17,
        items: [
            {
                name: 'Mini Desserts - Select 4',
                description: 'Flavored Mousse Cup (Chocolate, White Chocolate, Raspberry, Kahlua), Lemon Bars, Blondies, 7-Layer Bars, Brownies, Chocolate Chip Cookie Bars, Mini Assorted Cheesecakes, Fruit Tarts (Raspberry, Strawberry, Blackberry, Lemon, Lime)',
                unit_price: 5.25,
                price_type: 'per_person',
            },
            {
                name: 'Coffee Bar',
                description: 'Brewed In House Dunkin Donuts Coffee Served with: Sugar, Half & Half & Flavor Shots (Caramel, Hazelnut, French Vanilla)',
                unit_price: 2.75,
                price_type: 'per_person',
            },
        ],
    },
    {
        name: 'Wedding Cakes',
        sort_order: 18,
        items: [
            {
                name: 'Wedding/Tiered Cakes',
                description: '2 Tier 6" & 8" (Serves 25). Available Cakes: Yellow, White, Almond, Chocolate, Carrot, Red Velvet, Bananas Foster, Whiskey Caramel, Coconut. Fillings: Butter Cream, Lemon Curd, Raspberry Jam, Strawberry Jam, Cream Cheese Icing, Peanut Butter Cream, Mocha Buttercream, Salted Caramel Buttercream, Cinnamon Butter Cream. Buttercreams: Signature Buttercream, Chocolate Buttercream, Cream Cheese Frosting. Cupcakes - $3.50. For Additional Sizing, please send an inquiry.',
                unit_price: 275.00,
                price_type: 'flat',
                tags: ['wedding'],
            },
        ],
    },
    {
        name: 'Floral Arrangements - Rachel\'s Bloomers',
        sort_order: 19,
        items: [
            {
                name: 'Bridal Bouquets',
                description: 'Starting at $75',
                unit_price: 75.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
            {
                name: 'Bridesmaids Bouquets',
                description: 'Starting at $40',
                unit_price: 40.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
            {
                name: 'Corsages',
                description: 'Starting at $20',
                unit_price: 20.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
            {
                name: 'Boutonnieres',
                description: 'Starting at $15',
                unit_price: 15.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
            {
                name: 'Arbor Spray',
                description: 'Starting From $150',
                unit_price: 150.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
            {
                name: 'Table Runners',
                description: 'Starting From -$50',
                unit_price: 50.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
            {
                name: 'Center Pieces',
                description: 'Starting at $40',
                unit_price: 40.00,
                price_type: 'flat',
                tags: ['wedding', 'flowers'],
            },
        ],
    },
];
async function seedMenu() {
    console.log('🍽️  Starting menu seeding...\n');
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
                }
                catch (error) {
                    errors++;
                    console.error(`  ❌ Error creating item "${itemData.name}":`, error.message);
                }
            }
            console.log(`  ✅ Created ${categoryData.items.length} items`);
        }
        catch (error) {
            errors++;
            console.error(`❌ Error creating category "${categoryData.name}":`, error.message);
        }
    }
    console.log('\n' + '━'.repeat(50));
    console.log('📊 Menu Seeding Summary:');
    console.log('━'.repeat(50));
    console.log(`✅ Categories created: ${categoriesCreated}/${menuData.length}`);
    console.log(`✅ Menu items created: ${itemsCreated}`);
    console.log(`❌ Errors: ${errors}`);
    console.log('━'.repeat(50));
    console.log('\n📋 Sample Menu Items:\n');
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
            console.log(`  • ${item.name} - $${item.unit_price} ${item.price_type}`);
        }
        console.log('');
    }
}
async function seedPricingPackages() {
    console.log('\n💰 Creating pricing packages...\n');
    const packages = [
        {
            name: 'Bronze Package',
            description: 'Perfect for intimate gatherings (20-50 guests)',
            category: 'Standard',
            base_price: 20.00,
            price_type: 'per_person',
            priority: 1,
        },
        {
            name: 'Silver Package',
            description: 'Great for medium events (50-100 guests)',
            category: 'Standard',
            base_price: 25.00,
            price_type: 'per_person',
            priority: 2,
        },
        {
            name: 'Gold Package',
            description: 'Premium experience (100-200 guests)',
            category: 'Premium',
            base_price: 35.00,
            price_type: 'per_person',
            priority: 3,
        },
        {
            name: 'Platinum Package',
            description: 'Luxury catering for special occasions',
            category: 'Premium',
            base_price: 50.00,
            price_type: 'per_person',
            priority: 4,
        },
        {
            name: 'Wedding Package - Basic',
            description: 'Essential wedding catering',
            category: 'Wedding',
            base_price: 45.00,
            price_type: 'per_person',
            priority: 5,
        },
        {
            name: 'Wedding Package - Deluxe',
            description: 'Complete wedding catering with all services',
            category: 'Wedding',
            base_price: 65.00,
            price_type: 'per_person',
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
            console.log(`  ✅ Created: ${pkg.name}`);
        }
        catch (error) {
            console.error(`  ❌ Error creating "${pkg.name}":`, error.message);
        }
    }
    console.log(`\n✅ Created ${packagesCreated}/${packages.length} pricing packages\n`);
}
async function main() {
    try {
        console.log('🌱 FlashBack Catering - Menu & Pricing Seeder\n');
        const existingCategories = await prisma.menu_categories.count();
        const existingItems = await prisma.menu_items.count();
        const existingPackages = await prisma.pricing_packages.count();
        if (existingCategories > 0 || existingItems > 0) {
            console.log(`⚠️  Warning: Database already has ${existingCategories} categories and ${existingItems} menu items.`);
            console.log('This will add more data. To start fresh, clear the tables first.');
            console.log('Press Ctrl+C to cancel or wait 5 seconds to continue...\n');
            await new Promise((resolve) => setTimeout(resolve, 5000));
        }
        await seedMenu();
        await seedPricingPackages();
        console.log('━'.repeat(50));
        console.log('🎉 Seeding completed successfully!');
        console.log('━'.repeat(50));
        const totalCategories = await prisma.menu_categories.count();
        const totalItems = await prisma.menu_items.count();
        const totalPackages = await prisma.pricing_packages.count();
        console.log(`\n📊 Database totals:`);
        console.log(`   Menu Categories: ${totalCategories}`);
        console.log(`   Menu Items: ${totalItems}`);
        console.log(`   Pricing Packages: ${totalPackages}\n`);
    }
    catch (error) {
        console.error('❌ Seeding failed:', error);
        process.exit(1);
    }
    finally {
        await prisma.$disconnect();
    }
}
main();
//# sourceMappingURL=seed-menu.js.map