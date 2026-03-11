"""
Seed menu_categories, menu_items, and pricing_packages.
Run once: python database/seed_menu.py
"""

import asyncio
from prisma import Prisma

MENU_DATA = [
    {
        "name": "Hors D'oeuvres - Beef",
        "sort_order": 1,
        "items": [
            {"name": "Asian Roast Beef Crostini w/ Wasabi Aioli", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Adobo Steak Skewers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Meatballs (BBQ, Swedish, Sweet and Sour)", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Mexican Stuffed Peppers w/ Cojito Cheese", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Filet Tip Crostini", "unit_price": 3.50, "price_type": "per_person", "tags": ["premium"]},
        ],
    },
    {
        "name": "Hors D'oeuvres - Chicken",
        "sort_order": 2,
        "items": [
            {"name": "Maple Bacon Chicken Pops", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chicken Tikka Skewers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Adobo Lime Chicken Bites", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chicken Bahn Mi Slider w/ Jalapeno Slaw", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "BBQ Chicken Slider", "unit_price": 3.50, "price_type": "per_person"},
        ],
    },
    {
        "name": "Hors D'oeuvres - Pork",
        "sort_order": 3,
        "items": [
            {"name": "Smoked Pork Belly Dippers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Bacon Bourbon Meatballs", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Pulled Pork Sliders", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Chorizo Stuffed Baby Peppers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Twice Baked Potato Bites", "unit_price": 3.50, "price_type": "per_person"},
        ],
    },
    {
        "name": "Hors D'oeuvres - Seafood",
        "sort_order": 4,
        "items": [
            {"name": "Grilled Shrimp Cocktail", "unit_price": 4.75, "price_type": "per_person"},
            {"name": "Crab Stuffed Cucumbers", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "South West Shrimp Crostini", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Shrimp and Mango Bites", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Firecracker Shrimp", "unit_price": 4.75, "price_type": "per_person"},
            {"name": "Bacon Shrimp", "unit_price": 4.75, "price_type": "per_person"},
            {"name": "Crab Dip", "unit_price": 3.75, "price_type": "per_person"},
            {"name": "Ahi Tuna Bites", "unit_price": 3.50, "price_type": "per_person"},
        ],
    },
    {
        "name": "Hors D'oeuvres - Vegetarian",
        "sort_order": 5,
        "items": [
            {"name": "Par Pardon", "unit_price": 1.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Bruschetta", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Tomatoes and Feta", "unit_price": 1.95, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Chips and Salsa", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
            {"name": "Tomato & Guacamole", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
            {"name": "White Bean Tapenade w/ Crostini", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Artichoke Tapenade w/ Crostini", "unit_price": 1.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Caprese Skewers", "unit_price": 2.75, "price_type": "per_person", "tags": ["vegetarian"]},
        ],
    },
    {
        "name": "Hors D'oeuvres - Canapes",
        "sort_order": 6,
        "items": [
            {"name": "Smoked Salmon Phyllo Cups", "unit_price": 3.80, "price_type": "per_person"},
            {"name": "Tropical Cucumber Cups", "unit_price": 2.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Caviar Egg", "unit_price": 3.50, "price_type": "per_person"},
            {"name": "Caviar and Cream Crisp", "unit_price": 4.00, "price_type": "per_person"},
            {"name": "Charred Tomato and Pesto", "unit_price": 2.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Parmesan Artichoke Dip", "unit_price": 3.00, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Spanakopita", "unit_price": 3.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Brie & Cranberry Puff Cheese", "unit_price": 3.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Mac & Cheese Shooters", "unit_price": 3.25, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Bite Bites", "unit_price": 3.00, "price_type": "per_person"},
            {"name": "Double Stuffed Mushrooms", "unit_price": 2.75, "price_type": "per_person", "tags": ["vegetarian"]},
            {"name": "Gazpacho Shooters", "unit_price": 2.25, "price_type": "per_person", "tags": ["vegetarian", "vegan"]},
        ],
    },
    {
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
    {
        "name": "Signature Combinations",
        "sort_order": 8,
        "items": [
            {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person",
             "description": "Carved Prime Rib w/ Horseradish Cream & Aju, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, Glazed Carrots, Grilled Asparagus, Dinner Rolls"},
            {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person",
             "description": "Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls"},
            {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person",
             "description": "Chicken Piccata, Red Wine Braised Beef Roast, Long Grain Buttered Rice, Vegetable Farfalle, Roasted Mixed Veggies, Green Beans, Dinner Rolls"},
        ],
    },
    {
        "name": "BBQ Menus",
        "sort_order": 9,
        "items": [
            {"name": "Beef Brisket & Chicken", "unit_price": 25.99, "price_type": "per_person",
             "description": "BBQ Beef Brisket (sliced), Beer Can Chicken. Includes: Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad"},
            {"name": "Pork & Chicken", "unit_price": 23.99, "price_type": "per_person",
             "description": "Pulled BBQ Pork, Pulled BBQ Chicken. Includes: Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad"},
        ],
    },
    {
        "name": "Casual Fare - Burger Bar",
        "sort_order": 10,
        "items": [
            {"name": "Burger Bar", "unit_price": 23.99, "price_type": "per_person",
             "description": "Burgers (handmade) w/ Brioche Buns, Beer Can Chicken Breast. Toppings Bar: Mushrooms, Grilled Peppers and Onion, Pickles, Lettuce, Tomato, Bacon, Assorted Sauces and Cheese, Mac & Cheese, Roasted Red Potato"},
        ],
    },
    {
        "name": "Casual Fare - Southern Comfort",
        "sort_order": 11,
        "items": [
            {"name": "Southern Comfort", "unit_price": 27.95, "price_type": "per_person",
             "description": "Garden Salad, Crispy Fried Chicken, Smoked Sausage, Mac and Cheese, Mashed Potatoes, Southern Style Green Beans, Buttered Corn Kernel, Corn Bread w/ Butter"},
        ],
    },
    {
        "name": "Mexican",
        "sort_order": 12,
        "items": [
            {"name": "Char Grilled", "unit_price": 27.99, "price_type": "per_person",
             "description": "Carne Asada, Chili Lime Chicken, Spanish Rice, Bandito Black Beans, Peppers & Onions, Pico De Gallo, Sour Cream, Tortilla Shells"},
            {"name": "Fiesta Taco Bar", "unit_price": 23.99, "price_type": "per_person",
             "description": "Braised Spanish Beef, Braised Chili Chicken, Pinto Beans, Cilantro Lime Rice, Full Toppings Bar"},
        ],
    },
    {
        "name": "Mediterranean Bars",
        "sort_order": 13,
        "items": [
            {"name": "Mediterranean Bar", "unit_price": 23.49, "price_type": "per_person",
             "description": "Hummus Bar (all homemade), Roasted Garlic Hummus, Sundried Tomato Hummus, Original Hummus. Toppings: Grilled Marinated Chicken, Roasted Vegetables, Feta Cheese, Roasted Chickpeas, Olives, Fresh Diced Tomato, Pickled Onions"},
            {"name": "Souvlaki Bar", "unit_price": 21.49, "price_type": "per_person",
             "description": "Chicken Souvlaki, Tzatziki Sauce, Roasted Greek Potatoes, Roasted Mixed Vegetables, Green Beans, Pita Bread"},
        ],
    },
    {
        "name": "Italian Bars",
        "sort_order": 14,
        "items": [
            {"name": "Marsala Menu", "unit_price": 25.99, "price_type": "per_person",
             "description": "Chicken Marsala, Roasted Cod in Peperonata Sauce, Vegetable Farfalle, Fettuccini, Roasted Mixed Veggies, Green Beans, Dinner Rolls"},
            {"name": "Ravioli Menu", "unit_price": 31.99, "price_type": "per_person",
             "description": "Garden Salad, Grilled Chicken with Wild Mushroom Buer Blanc, Roasted Salmon w/ Lemon Butter Sauce, Truffle Ravioli, Wild Rice, Dinner Rolls"},
            {"name": "Grilled Pasta Menu", "unit_price": 21.99, "price_type": "per_person",
             "description": "Caesar Salad w/ Croutons, Grilled Chicken Breast, Sliced Italian Sausage, Pesto Penne Alfredo, Green Beans, Honey Glazed Carrots, Dinner Rolls"},
        ],
    },
    {
        "name": "Soup/Salad/Sandwich",
        "sort_order": 15,
        "items": [
            {"name": "Soup Pick 2", "unit_price": 21.95, "price_type": "per_person",
             "description": "Choose from: Broccoli Cheddar, Loaded Potato, Tomato Basil Bisque, Chicken Tortilla, Vegetable Minestrone, Clam Chowder, French Onion, Chicken Noodle, Chicken Chili"},
            {"name": "Salad Pick 2", "unit_price": 21.95, "price_type": "per_person",
             "description": "Choose from: Seasonal Greens Salad, Bacon and Blue Cheese Salad, Garden Salad, Southwest Salad, Pasta Salad, Potato Salad, Coleslaw"},
            {"name": "Sandwich Pick 2", "unit_price": 21.95, "price_type": "per_person",
             "description": "Choose from: Gourmet Grilled Cheese, Corned Beef and Reuben, Grilled Chicken, Avocado BLT, Pesto Chicken, Turkey Club, Philly Cheese Steaks"},
        ],
    },
    {
        "name": "Potato Bar",
        "sort_order": 16,
        "items": [
            {"name": "Potato Bar", "unit_price": 19.95, "price_type": "per_person",
             "description": "Choose Your Potato: Baked Idaho, Roasted Garlic Mashed, Sour Cream and Chive Mashed. Choose 2 Proteins and 8 Toppings from our selection"},
        ],
    },
    {
        "name": "Coffee and Desserts",
        "sort_order": 17,
        "items": [
            {"name": "Mini Desserts - Select 4", "unit_price": 5.25, "price_type": "per_person",
             "description": "Flavored Mousse Cup, Lemon Bars, Blondies, 7-Layer Bars, Brownies, Chocolate Chip Cookie Bars, Mini Assorted Cheesecakes, Fruit Tarts"},
            {"name": "Coffee Bar", "unit_price": 2.75, "price_type": "per_person",
             "description": "Brewed Dunkin Donuts Coffee with Sugar, Half & Half & Flavor Shots (Caramel, Hazelnut, French Vanilla)"},
        ],
    },
    {
        "name": "Wedding Cakes",
        "sort_order": 18,
        "items": [
            {"name": "Wedding/Tiered Cakes", "unit_price": 275.00, "price_type": "flat", "tags": ["wedding"],
             "description": "2 Tier 6\" & 8\" (Serves 25). Available: Yellow, White, Almond, Chocolate, Carrot, Red Velvet. Multiple filling and frosting options. Cupcakes $3.50 ea."},
        ],
    },
    {
        "name": "Floral Arrangements",
        "sort_order": 19,
        "items": [
            {"name": "Bridal Bouquets", "unit_price": 75.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
            {"name": "Bridesmaids Bouquets", "unit_price": 40.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
            {"name": "Corsages", "unit_price": 20.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
            {"name": "Boutonnieres", "unit_price": 15.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
            {"name": "Arbor Spray", "unit_price": 150.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
            {"name": "Table Runners", "unit_price": 50.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
            {"name": "Center Pieces", "unit_price": 40.00, "price_type": "flat", "tags": ["wedding", "flowers"]},
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


async def seed():
    client = Prisma()
    await client.connect()

    # Check existing data
    cat_count = await client.menu_categories.count()
    if cat_count > 0:
        print(f"Already seeded ({cat_count} categories). Skipping.")
        await client.disconnect()
        return

    items_created = 0

    for cat_data in MENU_DATA:
        cat = await client.menu_categories.create(
            data={"name": cat_data["name"], "sort_order": cat_data["sort_order"], "active": True}
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
    asyncio.run(seed())
