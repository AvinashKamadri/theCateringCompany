"""
Seed menu_categories, menu_items, and pricing_packages.
Run once: python database/seed_menu.py
Use --reseed to clear and re-populate all menu data.
"""

import sys
import asyncio
from prisma import Prisma

MENU_DATA = [
    # ─── HORS D'OEUVRES ───
    {
        "section": "Hors D'oeuvres",
        "name": "Chicken",
        "sort_order": 1,
        "items": [
            {"name": "Maple Bacon Chicken Pops", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chicken Tikka Skewers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Adobo Lime Chicken Bites", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chicken Banh Mi Slider w/ Jalapeno Slaw", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "BBQ Chicken Slider", "unit_price": 3.50, "price_type": "per_person"},
        ],
    },
    {
        "section": "Hors D'oeuvres",
        "name": "Pork",
        "sort_order": 2,
        "items": [
            {"name": "Smoked Pork Belly Dippers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Bacon Bourbon Meatballs", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Pulled Pork Sliders", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chorizo Stuffed Baby Peppers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Twice Baked Potato Bites", "unit_price": 3.50, "price_type": "per_person"},
        ],
    },
    {
        "section": "Hors D'oeuvres",
        "name": "Beef",
        "sort_order": 3,
        "items": [
            {"name": "Asian Roast Beef Crostini w/ Wasabi Aioli", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Adobo Steak Skewers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Meatballs (BBQ, Swedish, Sweet and Sour)", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Mexican Stuffed Peppers w/ Cojito Cheese", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Filet Tip Crostini", "unit_price": 4.50, "price_type": "per_person", "tags": ["premium"]},
        ],
    },
    {
        "section": "Hors D'oeuvres",
        "name": "Seafood",
        "sort_order": 4,
        "items": [
            {"name": "Grilled Shrimp Cocktail", "unit_price": 4.75, "price_type": "per_person"},
            {"name": "Crab Stuffed Cucumbers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "South West Shrimp Crostini", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Shrimp and Mango Bites", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Firecracker Shrimp", "unit_price": 4.75, "price_type": "per_person"},
            {"name": "Crab Cakes", "unit_price": 4.75, "price_type": "per_person"},
            {"name": "Crab Dip", "unit_price": 3.75, "price_type": "per_person"},
            {"name": "Ahi Tuna Bites", "unit_price": 3.50, "price_type": "per_person"},
        ],
    },
    {
        "section": "Hors D'oeuvres",
        "name": "Canapes",
        "sort_order": 5,
        "items": [
            {"name": "Smoked Salmon Phyllo Cups", "unit_price": 3.80, "price_type": "per_person"},
            {"name": "Tropical Cucumber Cups", "unit_price": 2.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Caviar Egg", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Caviar and Cream Crisp", "unit_price": 4.00, "price_type": "per_person"},
            {"name": "Charred Tomato and Pesto", "unit_price": 2.75, "price_type": "per_person", "tags": ["vegetarian"]},
        ],
    },
    {
        "section": "Hors D'oeuvres",
        "name": "Vegetarian",
        "sort_order": 6,
        "items": [
            {"name": "Bruschetta", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Hummus and Pita", "unit_price": 1.95, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Chips and Salsa", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
            {"name": "Chips & Guacamole", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
            {"name": "White Bean Tapenade w/ Crostini", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Artichoke Tapenade w/ Crostini", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Caprese Skewers", "unit_price": 2.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Parmesan Artichoke Dip", "unit_price": 3.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Spanakopita", "unit_price": 3.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Soft Pretzel Bites w/ Beer Cheese", "unit_price": 3.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Mac & Cheese Shooters", "unit_price": 3.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Double Stuffed Mushrooms", "unit_price": 2.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Gazpacho Shooters", "unit_price": 2.25, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
        ],
    },
    {
        "section": "Platters",
        "name": "Platters",
        "sort_order": 7,
        "items": [
            {"name": "Vegetable Platter", "unit_price": 2.25, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
            {"name": "Fruit Platter", "unit_price": 2.50, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
            {"name": "Assorted Finger Sandwiches", "unit_price": 4.00, "price_type": "per_person"},
            {"name": "Cheese Platter", "unit_price": 3.50, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Antipasto Platter", "unit_price": 3.35, "price_type": "per_person"},
            {"name": "Charcuterie Boards", "unit_price": 4.25, "price_type": "per_person"},
        ],
    },
    # ─── MAIN COURSES ───
    {
        "section": "Signature Combinations",
        "name": "Signature Combinations",
        "sort_order": 8,
        "items": [
            {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person",
             "description": "Carved Prime Rib w/ Horseradish Cream & Au Jus, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, Glazed Carrots, Grilled Asparagus, Dinner Rolls."},
            {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person",
             "description": "Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls."},
            {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person",
             "description": "Chicken Piccata, Red Wine Braised Beef Roast, Vegetable Farfalle, Long Grain Buttered Rice, Roasted Mixed Veggies, Green Beans, Dinner Rolls."},
        ],
    },
    {
        "section": "BBQ Menus",
        "name": "BBQ Menus",
        "sort_order": 9,
        "items": [
            {"name": "Beef Brisket & Chicken", "unit_price": 25.99, "price_type": "per_person",
             "description": "BBQ Beef Brisket (sliced), Beer Can Chicken. Sides: Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad."},
            {"name": "Pork & Chicken", "unit_price": 23.99, "price_type": "per_person",
             "description": "Pulled BBQ Pork, Pulled BBQ Chicken. Sides: Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad."},
        ],
    },
    {
        "section": "Tasty & Casual",
        "name": "Tasty & Casual",
        "sort_order": 10,
        "items": [
            {"name": "Burger Bar", "unit_price": 23.99, "price_type": "per_person",
             "description": "Burgers (handmade) w/ Brioche Buns, Beer Can Chicken Breast. Toppings Bar: Mushrooms, Grilled Onions, Pickled Red Onion, Pickles, Lettuce, Tomato, Bacon, Assorted Sauces and Cheeses. Sides: Mac & Cheese, Roasted Red Potato (Herb and Balsamic), Seasonal Spring Greens Salad, Caprese Platter, Watermelon Salad."},
            {"name": "Southern Comfort", "unit_price": 27.95, "price_type": "per_person",
             "description": "Garden Salad, Crispy Fried Chicken, Smoked Sausage, Mac and Cheese, Mashed Potatoes, Southern Style Green Beans, Buttered Corn Kernel, Corn Bread w/ Butter."},
        ],
    },
    {
        "section": "Global Inspirations",
        "name": "Global Inspirations",
        "sort_order": 11,
        "items": [
            {"name": "Mexican Char Grilled", "unit_price": 27.99, "price_type": "per_person",
             "description": "Carne Asada, Chili Lime Chicken, Spanish Rice, Bandito Black Beans, Peppers & Onions, Pico De Gallo, Sour Cream, Tortilla Shells."},
            {"name": "Fiesta Taco Bar", "unit_price": 23.99, "price_type": "per_person",
             "description": "Braised Spanish Beef, Braised Chili Chicken, Pinto Beans, Cilantro Lime Rice, Full Toppings Bar."},
            {"name": "Mediterranean Bar", "unit_price": 23.49, "price_type": "per_person",
             "description": "Hummus Bar (all homemade): Roasted Garlic, Sundried Tomato, Original. Toppings: Ground Lamb (hot), Grilled Mediterranean Chicken (hot), Roasted Vegetables (hot), Feta Cheese, Roasted Chickpeas, Olives, Fresh Diced Tomato, Pickled Onions, Caramelized Onions, Shredded Lettuce, Pita Bread."},
            {"name": "Souvlaki Bar", "unit_price": 21.49, "price_type": "per_person",
             "description": "Proteins: Chicken Souvlaki, Pork Souvlaki. Sides/Toppings: Roasted Greek Potatoes, Roasted Mixed Vegetables, Green Beans, Pita Bread, Fresh Diced Tomatoes, Diced Onions, Shredded Lettuce, Tzatziki, Feta Cheese, Fresh Cilantro."},
            {"name": "Marsala Menu", "unit_price": 25.99, "price_type": "per_person",
             "description": "Chicken Marsala, Roasted Cod in Peperonata Sauce, Vegetable Farfalle, Fettuccini, Roasted Mixed Veggies, Green Beans, Dinner Rolls."},
            {"name": "Ravioli Menu", "unit_price": 31.99, "price_type": "per_person",
             "description": "Garden Salad, Grilled Chicken with Wild Mushroom Beurre Blanc, Roasted Salmon w/ Lemon Butter Sauce, Truffle Ravioli, Wild Rice, Sauteed Zucchini and Tomatoes, Roasted Asparagus, Dinner Rolls."},
            {"name": "Grilled Pasta Menu", "unit_price": 21.49, "price_type": "per_person",
             "description": "Caesar Salad w/ Croutons on side, Grilled Chicken Breast, Sliced Italian Sausage, Pesto Penne Alfredo, Green Beans, Honey Glazed Carrots, Dinner Rolls."},
        ],
    },
    {
        "section": "Soup / Salad / Sandwich",
        "name": "Soup / Salad / Sandwich",
        "sort_order": 12,
        "items": [
            {"name": "Soup / Salad / Sandwich", "unit_price": 21.95, "price_type": "per_person",
             "description": (
                 "Soup (choose 1): Broccoli Cheddar, Loaded Potato, Tomato Basil Bisque, Chicken Tortilla, "
                 "Vegetable Minestrone, Clam Chowder, French Onion, Chicken Noodle, Traditional Chili, Chicken Chili. "
                 "Salad (choose 1): Caesar, Cobb, Greek, Southwest, Potato, Coleslaw, Seasonal Greens, Bacon and Blue Cheese, "
                 "Pasta, Sweet Kale w/ Bacon and Cranberries, Design Your Own. "
                 "Sandwich/Wrap (choose 1): Gourmet Grilled Cheese, Corned Beef Reuben, Pulled Pork Cuban, Avocado BLT, "
                 "Pesto Chicken, Turkey Club, Roasted Vegetable and Hummus Wrap, Philly Cheese Steak, Build Your Own."
             )},
        ],
    },
    # ─── DESSERTS ───
    {
        "section": "Coffee and Desserts",
        "name": "Mini Desserts",
        "sort_order": 13,
        "items": [
            # Select up to 4; $5.25 pp covers the whole dessert course
            {"name": "Flavored Mousse Cup",        "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"],
             "description": "Chocolate, White Chocolate, Raspberry, Kahlua"},
            {"name": "Lemon Bars",                 "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"]},
            {"name": "Blondies",                   "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"]},
            {"name": "7-Layer Bars",               "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"]},
            {"name": "Brownies",                   "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"]},
            {"name": "Chocolate Chip Cookie Bars", "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"]},
            {"name": "Mini Assorted Cheesecakes",  "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"]},
            {"name": "Fruit Tarts",                "unit_price": 5.25, "price_type": "per_person", "tags": ["dessert", "select-4"],
             "description": "Raspberry, Strawberry, Blackberry, Lemon, Lime"},
        ],
    },
    {
        "section": "Wedding / Tiered Cakes",
        "name": "Wedding / Tiered Cakes",
        "sort_order": 14,
        "items": [
            {"name": "Wedding/Tiered Cakes", "unit_price": 275.00, "price_type": "flat", "tags": ["wedding"],
             "description": (
                 "2 Tier 6\" & 8\" (Serves 25). Starts at $275. "
                 "Flavors: Yellow, White, Almond, Chocolate, Carrot, Red Velvet, Bananas Foster, Whiskey Caramel, "
                 "Lemon, Spice, Funfetti, Pumpkin Spice, Cookies and Cream, Strawberry, Coconut. "
                 "Fillings: Butter Cream, Lemon Curd, Raspberry Jam, Strawberry Jam, Cream Cheese Icing, "
                 "Peanut Butter Cream, Mocha Buttercream, Salted Caramel Buttercream, Cinnamon Butter Cream. "
                 "Buttercream: Signature, Chocolate, Cream Cheese Frosting."
             )},
            {"name": "Cupcakes", "unit_price": 3.50, "price_type": "per_unit", "tags": ["wedding"],
             "description": "Choice of two flavors. Custom colors available."},
        ],
    },
    # ─── DRINKS / COFFEE ───
    {
        "section": "Coffee and Desserts",
        "name": "Coffee and Drinks",
        "sort_order": 15,
        "items": [
            {"name": "Coffee Bar", "unit_price": 2.75, "price_type": "per_person",
             "description": "Brewed In House Dunkin Donuts Coffee served with Sugar, Half & Half, Flavor Shots (Caramel, Hazelnut, French Vanilla). Set out with dessert."},
        ],
    },
    # ─── BAR SUPPLIES (offered separately in bar/drinks flow) ───
    {
        "section": "Bar Supplies",
        "name": "Bar Supplies",
        "sort_order": 16,
        "items": [
            {"name": "Barback Package", "unit_price": 8.50, "price_type": "per_person",
             "description": "Diet Coke, Coke, Sprite, Ginger Ale, Club Soda, Tonic Water, Bitters, OJ, Cranberry and Pineapple Juices, Lemons, Limes and Oranges, Cherries, Ice, Clear Plastic Cups, Coolers."},
            {"name": "Ice & Cooler Package", "unit_price": 1.75, "price_type": "per_person",
             "description": "Ice (2 lbs per person @ $0.70/lb), Coolers included, Cups ($0.35 each)."},
        ],
    },
]

PRICING_PACKAGES = [
    {"name": "Bronze Package", "description": "Perfect for intimate gatherings (20-50 guests)", "category": "Standard", "base_price": 20.00, "price_type": "per_person", "priority": 1},
    {"name": "Silver Package", "description": "Great for medium events (50-100 guests)", "category": "Standard", "base_price": 25.00, "price_type": "per_person", "priority": 2},
    {"name": "Gold Package", "description": "Premium experience (100-200 guests)", "category": "Premium", "base_price": 35.00, "price_type": "per_person", "priority": 3},
    {"name": "Platinum Package", "description": "Luxury catering for special occasions", "category": "Premium", "base_price": 50.00, "price_type": "per_person", "priority": 4},
    {"name": "Wedding Package - Basic", "description": "Essential wedding catering", "category": "Wedding", "base_price": 45.00, "price_type": "per_person", "priority": 5},
    {"name": "Wedding Package - Deluxe", "description": "Complete wedding catering with all services", "category": "Wedding", "base_price": 65.00, "price_type": "per_person", "priority": 6},
]


async def seed(reseed: bool = False):
    client = Prisma()
    await client.connect()

    if reseed:
        print("Reseeding: clearing existing menu data...")
        await client.menu_items.delete_many()
        await client.menu_categories.delete_many()
        await client.pricing_packages.delete_many()
        print("  Cleared.")
    else:
        cat_count = await client.menu_categories.count()
        if cat_count > 0:
            print(f"Already seeded ({cat_count} categories). Use --reseed to re-populate.")
            await client.disconnect()
            return

    items_created = 0

    for cat_data in MENU_DATA:
        cat = await client.menu_categories.create(
            data={
                "section": cat_data.get("section", cat_data["name"]),
                "name": cat_data["name"],
                "sort_order": cat_data["sort_order"],
                "active": True,
            }
        )
        for item in cat_data["items"]:
            from decimal import Decimal
            await client.menu_items.create(
                data={
                    "category_id": cat.id,
                    "name": item["name"],
                    "description": item.get("description"),
                    "unit_price": Decimal(str(item["unit_price"])),
                    "price_type": item["price_type"],
                    "tags": item.get("tags", []),
                    "allergens": [],
                    "active": True,
                    "currency": "USD",
                }
            )
            items_created += 1
        print(f"  {cat_data['name']}: {len(cat_data['items'])} items")

    # Pricing packages
    for pkg in PRICING_PACKAGES:
        from decimal import Decimal
        await client.pricing_packages.create(
            data={
                "name": pkg["name"],
                "description": pkg["description"],
                "category": pkg["category"],
                "base_price": Decimal(str(pkg["base_price"])),
                "price_type": pkg["price_type"],
                "priority": pkg["priority"],
                "active": True,
                "currency": "USD",
            }
        )
    print(f"\nSeeded: {len(MENU_DATA)} categories, {items_created} items, {len(PRICING_PACKAGES)} packages")

    await client.disconnect()


if __name__ == "__main__":
    reseed_flag = "--reseed" in sys.argv
    asyncio.run(seed(reseed=reseed_flag))
