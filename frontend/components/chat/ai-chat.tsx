"use client";

import React, { useState, useEffect, useRef, Fragment } from 'react';
import { Send, Loader2, Sparkles, Check, ChevronDown } from 'lucide-react';
import { chatAiApi } from '@/lib/api/chat-ai';
import type { ChatMessage, ChatState, ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { CommandDialog } from './command-dialog';
import IntakeReviewPanel from './IntakeReviewPanel';

interface AiChatProps {
  projectId?: string;
  authorId?: string;
  userId?: string;
  userName?: string;
  initialThreadId?: string;
  onComplete?: (contractData: ContractData) => void;
  onThreadStart?: (threadId: string) => void;
  onSlotsUpdate?: (slots: Partial<ContractData>) => void;
  onProgressUpdate?: (progress: { filled: number; total: number }) => void;
}

const STORAGE_KEY = 'tc_chat_sessions';

// ─── Static menu category map (keyed by lowercase item name) ─────────────────
const ITEM_CATEGORY_MAP: Record<string, string> = {
  // Chicken
  'maple bacon chicken pops': 'Chicken',
  'chicken tikka skewers': 'Chicken',
  'adobo lime chicken bites': 'Chicken',
  'chicken satay': 'Chicken',
  'chicken banh mi slider w/ jalapeno slaw': 'Chicken',
  'chicken bahn mi slider w/ jalapeno slaw': 'Chicken',
  'bbq chicken slider': 'Chicken',
  // Pork
  'smoked pork belly dippers': 'Pork',
  'bacon bourbon meatballs': 'Pork',
  'pulled pork sliders': 'Pork',
  'chorizo stuffed baby peppers': 'Pork',
  'twice baked potato bites': 'Pork',
  // Beef
  'asian roast beef crostini w/ wasabi aioli': 'Beef',
  'adobo steak skewers': 'Beef',
  'meatballs (bbq, swedish, sweet and sour)': 'Beef',
  'mexican stuffed peppers w/ cojito cheese': 'Beef',
  'filet tip crostini': 'Beef',
  // Seafood
  'grilled shrimp cocktail': 'Seafood',
  'crab stuffed cucumbers': 'Seafood',
  'south west shrimp crostini': 'Seafood',
  'shrimp and mango bites': 'Seafood',
  'firecracker shrimp': 'Seafood',
  'crab cakes': 'Seafood',
  'crab dip': 'Seafood',
  'ahi tuna bites': 'Seafood',
  'bacon shrimp': 'Seafood',
  // Canapes
  'smoked salmon phyllo cups': 'Canapes',
  'tropical cucumber cups': 'Canapes',
  'deviled egg': 'Canapes',
  'caviar egg': 'Canapes',
  'caviar and cream crisp': 'Canapes',
  'charred tomato and pesto': 'Canapes',
  // Vegetarian
  'bruschetta': 'Vegetarian',
  'hummus and pita': 'Vegetarian',
  'chips and salsa': 'Vegetarian',
  'chips & guacamole': 'Vegetarian',
  'chips and guacamole': 'Vegetarian',
  'white bean tapenade w/ crostini': 'Vegetarian',
  'artichoke tapenade w/ crostini': 'Vegetarian',
  'caprese skewers': 'Vegetarian',
  'parmesan artichoke dip': 'Vegetarian',
  'spanakopita': 'Vegetarian',
  'soft pretzel bites w/ beer cheese': 'Vegetarian',
  'mac & cheese shooters': 'Vegetarian',
  'brie bites': 'Vegetarian',
  'double stuffed mushrooms': 'Vegetarian',
  'gazpacho shooters': 'Vegetarian',
  // misc legacy names
  'bite bites': 'Vegetarian',
  'brie & cranberry puff cheese': 'Vegetarian',
  'par pardon': 'Vegetarian',
  'tomato & guacamole': 'Vegetarian',
  'tomatoes and feta': 'Vegetarian',
};

// Main menu item → category map
const MAIN_ITEM_CATEGORY_MAP: Record<string, string> = {
  // Platters
  'vegetable platter': 'Platters',
  'fruit platter': 'Platters',
  'assorted finger sandwiches': 'Platters',
  'cheese platter': 'Platters',
  'antipasto platter': 'Platters',
  'charcuterie boards': 'Platters',
  'charcuterie board': 'Platters',
  // Signature Combinations
  'prime rib & salmon': 'Signature Combos',
  'prime rib and salmon': 'Signature Combos',
  'chicken & ham': 'Signature Combos',
  'chicken and ham': 'Signature Combos',
  'grilled chicken and ham': 'Signature Combos',
  'chicken piccata': 'Signature Combos',
  'chicken piccata and red wine braised beef': 'Signature Combos',
  'chicken piccata & red wine braised beef': 'Signature Combos',
  // BBQ Menus
  'beef brisket & chicken': 'BBQ Menus',
  'beef brisket and chicken': 'BBQ Menus',
  'pork & chicken': 'BBQ Menus',
  'pork and chicken': 'BBQ Menus',
  // Tasty & Casual
  'burger bar': 'Tasty & Casual',
  'southern comfort': 'Tasty & Casual',
  // Global Inspirations
  'mexican char grilled': 'Global Inspirations',
  'fiesta taco bar': 'Global Inspirations',
  'mediterranean bar': 'Global Inspirations',
  'souvlaki bar': 'Global Inspirations',
  'marsala menu': 'Global Inspirations',
  'ravioli menu': 'Global Inspirations',
  'grilled pasta menu': 'Global Inspirations',
  // Soup / Salad / Sandwich
  'soup / salad / sandwich menu': 'Soup / Salad / Sandwich',
  'soup/salad/sandwich menu': 'Soup / Salad / Sandwich',
  'soup salad sandwich menu': 'Soup / Salad / Sandwich',
  // Desserts
  'flavored mousse cup': 'Desserts',
  'lemon bars': 'Desserts',
  'blondies': 'Desserts',
  '7-layer bars': 'Desserts',
  'brownies': 'Desserts',
  'chocolate chip cookie bars': 'Desserts',
  'mini assorted cheesecakes': 'Desserts',
  'fruit tarts': 'Desserts',
  // Coffee & Bar
  'coffee bar': 'Coffee & Bar',
  'barback package': 'Coffee & Bar',
  'ice & cooler package': 'Coffee & Bar',
  'ice and cooler package': 'Coffee & Bar',
  // Wedding Cakes
  '2 tier 6" & 8" (serves 25)': 'Wedding Cakes',
  '2 tier': 'Wedding Cakes',
  'cupcakes': 'Wedding Cakes',
  'wedding cake': 'Wedding Cakes',
  'tiered cake': 'Wedding Cakes',
  'tiered cakes': 'Wedding Cakes',
};

const CATEGORY_ORDER = ['Chicken', 'Pork', 'Beef', 'Seafood', 'Canapes', 'Vegetarian'];
const MAIN_CATEGORY_ORDER = ['Platters', 'Signature Combos', 'BBQ Menus', 'Tasty & Casual', 'Global Inspirations', 'Soup / Salad / Sandwich', 'Desserts', 'Coffee & Bar', 'Wedding Cakes'];

function groupItemsByCategory(items: ListItem[]): CategoryGroup[] | null {
  const map = new Map<string, ListItem[]>();
  const uncategorizedItems: ListItem[] = [];
  // Try appetizer map first, then main menu map; enrich with descriptions
  for (const item of items) {
    const key = item.name.toLowerCase();
    const cat = ITEM_CATEGORY_MAP[key] ?? MAIN_ITEM_CATEGORY_MAP[key];
    const desc = ITEM_DESCRIPTIONS[key];
    const enriched = desc ? { ...item, description: desc } : item;
    if (!cat) { uncategorizedItems.push(enriched); continue; }
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat)!.push(enriched);
  }
  if (map.size < 2 || uncategorizedItems.length > items.length * 0.4) return null;
  // Use appetizer order if appetizer categories present, else main menu order
  const isMain = [...map.keys()].some((k) => MAIN_CATEGORY_ORDER.includes(k));
  const order = isMain ? MAIN_CATEGORY_ORDER : CATEGORY_ORDER;
  const groups = order
    .filter((c) => map.has(c))
    .map((c) => ({ category: c, items: map.get(c)! }));
  // Append any uncategorized items under "Other"
  if (uncategorizedItems.length > 0) {
    groups.push({ category: 'Other', items: uncategorizedItems });
  }
  return groups;
}

// ─── List parsing ─────────────────────────────────────────────────────────────

interface ListItem {
  name: string;
  price?: string;
  description?: string;
}

// Descriptions for items that need detail display (Coffee & Bar, Signature Combos, etc.)
const ITEM_DESCRIPTIONS: Record<string, string> = {
  'coffee bar': 'Brewed In House Dunkin Donuts Coffee with Sugar, Half & Half, Flavor Shots (Caramel, Hazelnut, French Vanilla). Set out with dessert.',
  'barback package': 'Diet Coke, Coke, Sprite, Ginger Ale, Club Soda, Tonic Water, Bitters, OJ, Cranberry & Pineapple Juices, Lemons, Limes, Oranges, Cherries, Ice, Cups, Coolers.',
  'ice & cooler package': 'Ice (2 lbs/person @ $0.70/lb), Coolers included, Cups ($0.35 each).',
  'ice and cooler package': 'Ice (2 lbs/person @ $0.70/lb), Coolers included, Cups ($0.35 each).',
  // Signature Combos
  'prime rib & salmon': 'Carved Prime Rib w/ Horseradish Cream & Au Jus, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, Glazed Carrots, Grilled Asparagus, Dinner Rolls.',
  'prime rib and salmon': 'Carved Prime Rib w/ Horseradish Cream & Au Jus, Roasted Salmon w/ Dill Cream Sauce, Roasted Potatoes, Wild Rice, Glazed Carrots, Grilled Asparagus, Dinner Rolls.',
  'chicken & ham': 'Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls.',
  'chicken and ham': 'Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls.',
  'grilled chicken and ham': 'Grilled Chicken Breast, Mango Glazed Ham Carved, Mashed Potatoes, Rice Pilaf, Buttered Corn, Green Beans, Dinner Rolls.',
  'chicken piccata': 'Chicken Piccata, Red Wine Braised Beef Roast, Vegetable Farfalle, Long Grain Buttered Rice, Roasted Mixed Veggies, Green Beans, Dinner Rolls.',
  'chicken piccata and red wine braised beef': 'Chicken Piccata, Red Wine Braised Beef Roast, Vegetable Farfalle, Long Grain Buttered Rice, Roasted Mixed Veggies, Green Beans, Dinner Rolls.',
  // BBQ
  'beef brisket & chicken': 'BBQ Beef Brisket (sliced), Beer Can Chicken. Includes Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad.',
  'beef brisket and chicken': 'BBQ Beef Brisket (sliced), Beer Can Chicken. Includes Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad.',
  'pork & chicken': 'Pulled BBQ Pork, Pulled BBQ Chicken. Includes Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad.',
  'pork and chicken': 'Pulled BBQ Pork, Pulled BBQ Chicken. Includes Mac & Cheese, Baked Beans, Coleslaw, Pasta Salad, Potato Salad.',
  // Tasty & Casual
  'burger bar': 'Handmade Burgers w/ Brioche Buns, Beer Can Chicken. Toppings Bar, Mac & Cheese, Roasted Potatoes, Spring Greens, Caprese Platter, Watermelon Salad.',
  'southern comfort': 'Crispy Fried Chicken, Smoked Sausage, Mac & Cheese, Mashed Potatoes, Southern Green Beans, Buttered Corn, Corn Bread.',
  // Global
  'mexican char grilled': 'Carne Asada, Chili Lime Chicken, Spanish Rice, Black Beans, Peppers & Onions, Pico De Gallo, Sour Cream, Tortilla Shells.',
  'fiesta taco bar': 'Braised Spanish Beef, Braised Chili Chicken, Pinto Beans, Cilantro Lime Rice, Full Toppings Bar.',
  'mediterranean bar': 'Hummus Bar (Roasted Garlic, Sundried Tomato, Original), Grilled Chicken, Ground Lamb, Roasted Veggies, Feta, Pita Bread & more.',
  'souvlaki bar': 'Chicken & Pork Souvlaki, Greek Potatoes, Roasted Veggies, Green Beans, Pita, Tzatziki, Feta.',
  'marsala menu': 'Chicken Marsala, Roasted Cod in Peperonata Sauce, Vegetable Farfalle, Fettuccini, Roasted Veggies, Green Beans, Dinner Rolls.',
  'ravioli menu': 'Grilled Chicken w/ Wild Mushroom Beurre Blanc, Roasted Salmon, Truffle Ravioli, Wild Rice, Sauteed Zucchini, Roasted Asparagus, Dinner Rolls.',
  'grilled pasta menu': 'Grilled Chicken Breast, Sliced Italian Sausage, Pesto Penne Alfredo, Green Beans, Honey Glazed Carrots, Dinner Rolls.',
  // Soup/Salad/Sandwich
  'soup / salad / sandwich menu': 'Pick 2 Soups, 2 Salads, 2 Sandwiches/Wraps from our selection.',
  'soup/salad/sandwich menu': 'Pick 2 Soups, 2 Salads, 2 Sandwiches/Wraps from our selection.',
};

interface CategoryGroup {
  category: string;
  items: ListItem[];
}

function parseCategorizedItems(content: string): CategoryGroup[] | null {
  const lines = content.split('\n');
  const groups: CategoryGroup[] = [];
  let current: CategoryGroup | null = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    // Category header: a line that's NOT a numbered item, has text, no leading number+dot
    // e.g. "Chicken ($3.50 pp/option)" or "Beef" or "Vegetarian"
    const isNumbered = /^(\d+)\.\s+/.test(trimmed);
    const isBullet = /^[-•*]\s+/.test(trimmed);
    const looksLikeCategory = !isNumbered && !isBullet && trimmed.length > 1 && trimmed.length < 60
      && /^[A-Z]/.test(trimmed) && !/^(Pick|Choose|Are|Here|Got|Sounds|The|I |You|We |If |Please)/i.test(trimmed);

    if (looksLikeCategory && !isNumbered) {
      // Extract category name (strip price annotation)
      const catName = trimmed.replace(/\s*\(.*?\)\s*$/, '').trim();
      if (catName.length > 1) {
        current = { category: catName, items: [] };
        groups.push(current);
        continue;
      }
    }

    // Parse item line
    const withPrice = trimmed.match(/^(?:\d+\.|[-•*])\s+(.+?)\s+\((\$[\d.,]+[^)]*)\)/);
    if (withPrice) {
      if (!current) { current = { category: '', items: [] }; groups.push(current); }
      current.items.push({ name: withPrice[1].trim(), price: withPrice[2].trim() });
      continue;
    }
    const plain = trimmed.match(/^(\d+)\.\s+(.{2,80})$/);
    if (plain) {
      if (!current) { current = { category: '', items: [] }; groups.push(current); }
      current.items.push({ name: plain[2].trim() });
    }
  }

  const valid = groups.filter((g) => g.items.length > 0);
  return valid.length >= 2 ? valid : null;
}

// Detect yes/no questions → return synthetic Yes/No cards
const YES_NO_PATTERNS = [
  /would you like to add/i,
  /would you like us to/i,
  /would you like to schedule/i,
  /do you (need|want) any/i,
  /do you (need|want) (rental|utensil|linen|floral)/i,
  /do you want to add anything/i,
  /is that the final/i,
  /are you all set/i,
  /anything else you (need|want|like)/i,
  /is there anything else/i,
  /any (special request|dietary|health|allerg)/i,
  /yes or no\??/i,
  /\b(need|want|like)\b.*(utensil|plate|napkin|silverware|cutlery)/i,
  /\b(need|want|like)\b.*(rental|tent|chair|table|linen)/i,
  /\b(need|want|like)\b.*(floral|flower|decoration|centerpiece)/i,
  /\b(need|want|like)\b.*(coffee|bar setup|bar service)/i,
];

function isYesNoQuestion(content: string): boolean {
  const lower = content.toLowerCase();
  // Skip if already has a numbered/bulleted list
  if (/^\s*\d+\./m.test(content) || /^\s*[-•*]\s/m.test(content)) return false;
  return YES_NO_PATTERNS.some((p) => p.test(content));
}

function parseListItems(content: string): ListItem[] | null {
  // Check if it's a yes/no question → return synthetic Yes/No items
  if (isYesNoQuestion(content)) {
    return [{ name: 'Yes' }, { name: 'No' }];
  }

  const items: ListItem[] = [];

  // First try line-by-line (normal multiline lists)
  const lines = content.split('\n');
  for (const line of lines) {
    const withPrice = line.match(/^(?:\d+\.|[-•*])\s+(.+?)\s+\((\$[\d.,]+[^)]*)\)/);
    if (withPrice) { items.push({ name: withPrice[1].trim(), price: withPrice[2].trim() }); continue; }
    const plain = line.match(/^(\d+)\.\s+(.{2,60})$/);
    if (plain) items.push({ name: plain[2].trim() });
  }
  if (items.length >= 2) return items;

  // Fallback: inline numbered list e.g. "1. Wedding 2. Birthday 3. Corporate"
  const inlineMatches = content.matchAll(/\d+\.\s+([A-Za-z][A-Za-z &'-]{1,40})(?=\s+\d+\.|$)/g);
  const inlineItems: ListItem[] = [];
  for (const m of inlineMatches) inlineItems.push({ name: m[1].trim() });
  if (inlineItems.length >= 2) return inlineItems;

  return null;
}

// Multi-select: items with prices AND more than 5 options (e.g. appetizers, mains).
// Single-select: no prices (event types, cake flavors, fillings, buttercreams).
function isMultiSelect(items: ListItem[]): boolean {
  const withPrices = items.filter((i) => i.price).length;
  return withPrices > 0 && items.length > 5;
}

// Confirmation messages list selected items — should be read-only, not interactive.
const CONFIRM_PATTERNS = [
  /just to confirm/i,
  /your (menu|selection|order|choices?) (includes?|contains?|is)/i,
  /to confirm.{0,30}(your|the) (menu|selection)/i,
  /here'?s? (a )?summary/i,
  /you('ve| have) selected/i,
  /confirming your/i,
];
function isConfirmationMessage(intro: string): boolean {
  return CONFIRM_PATTERNS.some((p) => p.test(intro));
}

function splitAtList(content: string): { intro: string } {
  const firstListLine = content.search(/^(?:\d+\.|[-•*])\s+/m);
  if (firstListLine === -1) return { intro: content };
  return { intro: content.slice(0, firstListLine).trimEnd() };
}

// ─── Option card (single-select square) ───────────────────────────────────────

function OptionCard({
  item,
  selected,
  onToggle,
}: {
  item: ListItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`relative flex flex-col items-start justify-end rounded-xl border-2 p-3 text-left transition-all focus:outline-none w-full ${
        item.description ? 'min-h-[80px]' : 'h-20'
      } ${
        selected
          ? 'border-black bg-black text-white'
          : 'border-neutral-200 bg-white hover:border-neutral-400 text-neutral-900'
      }`}
    >
      {selected && (
        <div className="absolute top-2.5 right-2.5 w-5 h-5 bg-white rounded-full flex items-center justify-center shadow">
          <Check className="w-3 h-3 text-black" strokeWidth={3} />
        </div>
      )}
      <span className="text-sm font-semibold leading-tight">{item.name}</span>
      {item.price && (
        <span className={`text-xs mt-0.5 ${selected ? 'text-neutral-300' : 'text-neutral-400'}`}>
          {item.price}
        </span>
      )}
      {item.description && (
        <span className={`text-[10px] mt-1 leading-snug line-clamp-2 ${selected ? 'text-neutral-300' : 'text-neutral-400'}`}>
          {item.description}
        </span>
      )}
    </button>
  );
}

// ─── Multi-select grid (menu items with prices) ───────────────────────────────

function MenuItemCard({
  item,
  selected,
  onToggle,
}: {
  item: ListItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`relative flex flex-col rounded-xl border-2 overflow-hidden text-left transition-all focus:outline-none ${
        selected ? 'border-black bg-black/5 shadow-sm' : 'border-neutral-200 bg-white hover:border-neutral-400'
      }`}
    >
      {!item.description && <div className="w-full h-14 bg-neutral-100" />}
      {selected && (
        <div className="absolute top-1.5 right-1.5 w-5 h-5 bg-black rounded-full flex items-center justify-center shadow">
          <Check className="w-3 h-3 text-white" strokeWidth={3} />
        </div>
      )}
      <div className="p-2 flex-1">
        <p className="text-xs font-semibold text-neutral-900 leading-tight line-clamp-2">{item.name}</p>
        {item.price && <p className="text-xs text-neutral-500 mt-0.5">{item.price}</p>}
        {item.description && (
          <p className="text-[10px] text-neutral-400 mt-1 leading-snug line-clamp-3">{item.description}</p>
        )}
      </div>
    </button>
  );
}

// ─── Unified list UI ──────────────────────────────────────────────────────────

function ItemSelector({
  items,
  categories,
  selected,
  onSelectionChange,
  multi,
  maxSelect,
}: {
  items: ListItem[];
  categories?: CategoryGroup[];
  selected: string[];
  onSelectionChange: (names: string[]) => void;
  multi: boolean;
  maxSelect?: number;
}) {
  const toggle = (name: string) => {
    if (multi) {
      const isSelected = selected.includes(name);
      if (isSelected) {
        onSelectionChange(selected.filter((n) => n !== name));
      } else if (!maxSelect || selected.length < maxSelect) {
        onSelectionChange([...selected, name]);
      }
    } else {
      onSelectionChange(selected.includes(name) ? [] : [name]);
    }
  };

  if (multi) {
    if (categories && categories.length >= 2) {
      return (
        <div className="mt-2 w-full space-y-4">
          {categories.map((group) => (
            <div key={group.category}>
              {group.category && (
                <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
                  {group.category}
                </p>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {group.items.map((item) => (
                  <MenuItemCard key={item.name} item={item} selected={selected.includes(item.name)} onToggle={() => toggle(item.name)} />
                ))}
              </div>
            </div>
          ))}
          {selected.length > 0 && (
            <p className="text-xs text-neutral-500 mt-2">
              <span className="font-medium text-neutral-800">{selected.length}</span>
              {maxSelect ? `/${maxSelect}` : ''} selected — hit Send to confirm
            </p>
          )}
        </div>
      );
    }

    return (
      <div className="mt-2 w-full">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {items.map((item) => (
            <MenuItemCard key={item.name} item={item} selected={selected.includes(item.name)} onToggle={() => toggle(item.name)} />
          ))}
        </div>
        {selected.length > 0 && (
          <p className="text-xs text-neutral-500 mt-2">
            <span className="font-medium text-neutral-800">{selected.length}</span>
            {maxSelect ? `/${maxSelect}` : ''} selected — hit Send to confirm
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="mt-2 w-full">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {items.map((item) => (
          <OptionCard key={item.name} item={item} selected={selected.includes(item.name)} onToggle={() => toggle(item.name)} />
        ))}
      </div>
      {selected.length > 0 && (
        <p className="text-xs text-neutral-500 mt-1">Hit Send to confirm</p>
      )}
    </div>
  );
}

// ─── Markdown renderer ────────────────────────────────────────────────────────

function MarkdownMessage({ content }: { content: string }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    const headingMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const Tag = (`h${level}`) as keyof React.JSX.IntrinsicElements;
      const cls = level === 1 ? 'font-bold text-base mt-2 mb-1' : level === 2 ? 'font-semibold text-sm mt-2 mb-1' : 'font-semibold text-sm mt-1';
      elements.push(<Tag key={i} className={cls}>{inlineFormat(text)}</Tag>);
      i++; continue;
    }

    const numMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\d+)\.\s+(.*)/);
        if (!m) break;
        listItems.push(
          <li key={i} className="flex gap-2 text-sm">
            <span className="text-neutral-400 shrink-0 w-5 text-right">{m[1]}.</span>
            <span>{inlineFormat(m[2])}</span>
          </li>
        );
        i++;
      }
      elements.push(<ol key={`ol-${i}`} className="space-y-1 my-1">{listItems}</ol>);
      continue;
    }

    const bulletMatch = line.match(/^[-*•]\s+(.*)/);
    if (bulletMatch) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^[-*•]\s+(.*)/);
        if (!m) break;
        listItems.push(
          <li key={i} className="flex gap-2 text-sm">
            <span className="text-neutral-400 shrink-0">•</span>
            <span>{inlineFormat(m[1])}</span>
          </li>
        );
        i++;
      }
      elements.push(<ul key={`ul-${i}`} className="space-y-1 my-1">{listItems}</ul>);
      continue;
    }

    if (line.trim() === '') {
      elements.push(<div key={i} className="h-1" />);
      i++; continue;
    }

    elements.push(<p key={i} className="text-sm">{inlineFormat(line)}</p>);
    i++;
  }

  return <div className="space-y-0.5">{elements}</div>;
}

function inlineFormat(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*'))
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith('`') && part.endsWith('`'))
      return <code key={i} className="bg-neutral-200 rounded px-1 text-xs font-mono">{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

// ─── Session storage ──────────────────────────────────────────────────────────

function saveSessionToStorage(threadId: string) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const sessions: { threadId: string; startedAt: string; lastActiveAt: string }[] =
      raw ? JSON.parse(raw) : [];
    const idx = sessions.findIndex((s) => s.threadId === threadId);
    const now = new Date().toISOString();
    if (idx >= 0) {
      sessions[idx].lastActiveAt = now;
    } else {
      sessions.push({ threadId, startedAt: now, lastActiveAt: now });
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // localStorage unavailable — ignore
  }
}

// ─── Country codes ────────────────────────────────────────────────────────────
const COUNTRY_CODES = [
  { code: '+1',  flag: '🇺🇸', name: 'US' },
  { code: '+1',  flag: '🇨🇦', name: 'CA' },
  { code: '+44', flag: '🇬🇧', name: 'GB' },
  { code: '+91', flag: '🇮🇳', name: 'IN' },
  { code: '+61', flag: '🇦🇺', name: 'AU' },
  { code: '+64', flag: '🇳🇿', name: 'NZ' },
  { code: '+971', flag: '🇦🇪', name: 'AE' },
  { code: '+65', flag: '🇸🇬', name: 'SG' },
  { code: '+60', flag: '🇲🇾', name: 'MY' },
  { code: '+63', flag: '🇵🇭', name: 'PH' },
  { code: '+852', flag: '🇭🇰', name: 'HK' },
  { code: '+49', flag: '🇩🇪', name: 'DE' },
  { code: '+33', flag: '🇫🇷', name: 'FR' },
  { code: '+39', flag: '🇮🇹', name: 'IT' },
  { code: '+34', flag: '🇪🇸', name: 'ES' },
  { code: '+55', flag: '🇧🇷', name: 'BR' },
  { code: '+52', flag: '🇲🇽', name: 'MX' },
  { code: '+81', flag: '🇯🇵', name: 'JP' },
  { code: '+82', flag: '🇰🇷', name: 'KR' },
  { code: '+86', flag: '🇨🇳', name: 'CN' },
];

function isAskingForPhone(content: string): boolean {
  const lower = content.toLowerCase();
  return (lower.includes('phone') || lower.includes('mobile') || lower.includes('number to reach')) &&
    !lower.includes('guest') && !lower.includes('how many');
}

function isAskingForEmail(content: string): boolean {
  const lower = content.toLowerCase();
  return lower.includes('email') && !lower.includes('we\'ll') && !lower.includes('confirmation');
}

function isAskingForDate(content: string): boolean {
  const lower = content.toLowerCase();
  return (lower.includes('event date') || lower.includes('when is') || lower.includes('what date') ||
    lower.includes('when\'s the') || lower.includes('the big day') || lower.includes('when is the big day') ||
    lower.includes('celebration happening') || lower.includes('when\'s your') ||
    (lower.includes('date') && (lower.includes('have in mind') || lower.includes('planning'))));
}

// ─── Main component ───────────────────────────────────────────────────────────

export function AiChat({ projectId, authorId, userId, userName = 'You', initialThreadId, onComplete, onThreadStart, onSlotsUpdate, onProgressUpdate }: AiChatProps) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: { filled: 0, total: 20 },
    isComplete: false,
  });
  const [input, setInput] = useState('');
  const [countryCode, setCountryCode] = useState(COUNTRY_CODES[0]);
  const [menuSelections, setMenuSelections] = useState<string[]>([]);
  const [activeMenuMsgIdx, setActiveMenuMsgIdx] = useState<number | null>(null);
  const [commandDialog, setCommandDialog] = useState<{ isOpen: boolean; command: 'menu' | 'events' | null }>({
    isOpen: false,
    command: null,
  });
  // Frontend-only intercept flows (contact info, wedding cake)
  type FrontendStep =
    | null
    | 'contact_email' | 'contact_phone'
    | 'cake_ask' | 'cake_flavor' | 'cake_filling' | 'cake_buttercream';
  const [frontendStep, setFrontendStep] = useState<FrontendStep>(null);
  const contactAskedRef = useRef(false);
  const weddingCakeAskedRef = useRef(false);
  const deferredAiMessageRef = useRef<ChatMessage | null>(null);
  const weddingCakeDataRef = useRef<{ flavor?: string; filling?: string; buttercream?: string }>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const startedRef = useRef(false);
  const lastSlotsFilled = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  // Keep input focused after every message
  useEffect(() => {
    if (!state.isLoading) inputRef.current?.focus();
  }, [state.isLoading, state.messages]);

  // When messages change, activate last AI message with a list if it's the latest message
  useEffect(() => {
    let lastListIdx: number | null = null;
    state.messages.forEach((msg, idx) => {
      if (msg.role === 'ai' && parseListItems(msg.content)) lastListIdx = idx;
    });
    const lastMsgIdx = state.messages.length - 1;
    if (lastListIdx !== null && lastListIdx === lastMsgIdx) {
      setActiveMenuMsgIdx(lastListIdx);
    } else {
      setActiveMenuMsgIdx(null);
    }
  }, [state.messages]);

  // Sync menu selections to input
  const handleMenuSelectionChange = (names: string[]) => {
    setMenuSelections(names);
    setInput(names.join(', '));
  };

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    if (initialThreadId) {
      loadConversationHistory(initialThreadId);
    } else {
      handleSendMessage('Hello! I need help planning my event.');
    }
  }, []);

  useEffect(() => {
    const handleHelp = () => {
      handleSendMessage('/help - I need assistance from your team');
    };
    window.addEventListener('chat:help', handleHelp);
    return () => window.removeEventListener('chat:help', handleHelp);
  }, []);

  async function loadConversationHistory(threadId: string) {
    setState((prev) => ({ ...prev, isLoading: true }));
    try {
      const conv = await chatAiApi.getConversation(threadId);
      const messages: ChatMessage[] = (conv.messages ?? []).map((m: any) => ({
        role: m.sender_type === 'user' ? 'user' : 'ai',
        content: m.content,
        timestamp: new Date(m.created_at),
      }));
      setState((prev) => ({
        ...prev,
        messages,
        threadId,
        progress: { filled: conv.slots_filled ?? 0, total: 20 },
        isComplete: conv.is_completed ?? false,
        isLoading: false,
      }));
      saveSessionToStorage(threadId);
      onThreadStart?.(threadId);
      if (conv.slots) {
        onSlotsUpdate?.(conv.slots);
        // Don't re-ask frontend questions on conversation reload
        if (conv.slots.name) contactAskedRef.current = true;
        if (conv.slots.event_type && /wedding/i.test(String(conv.slots.event_type))) {
          weddingCakeAskedRef.current = true;
        }
      }
      onProgressUpdate?.({ filled: conv.slots_filled ?? 0, total: 20 });
      if (conv.is_completed && conv.slots) {
        setState((prev) => ({ ...prev, contractData: { ...conv.slots, thread_id: threadId } as any }));
      }
    } catch {
      setState((prev) => ({ ...prev, isLoading: false }));
      toast.error('Could not load conversation history.');
    }
  }

  const handleSendMessage = async (messageText?: string) => {
    const content = messageText || input.trim();
    if (!content || state.isLoading) return;

    // ─── Re-trigger wedding cake via "@ai change cake" ───────────────
    if (!frontendStep && weddingCakeAskedRef.current && /(@ai\s+)?(change|update|redo|edit)\s*(wedding\s*)?cake/i.test(content)) {
      const userMsg: ChatMessage = { role: 'user', content, timestamp: new Date() };
      setInput(''); setMenuSelections([]); setActiveMenuMsgIdx(null);
      weddingCakeDataRef.current = {};
      deferredAiMessageRef.current = null;
      const ask: ChatMessage = { role: 'ai', content: '🎂 Would you like a wedding cake?\n1. Yes\n2. No thanks', timestamp: new Date() };
      setState((prev) => ({ ...prev, messages: [...prev.messages, userMsg, ask] }));
      setFrontendStep('cake_ask');
      return;
    }

    // ─── Frontend-only step interception ──────────────────────────────
    if (frontendStep) {
      const userMsg: ChatMessage = { role: 'user', content, timestamp: new Date() };
      setInput(''); setMenuSelections([]); setActiveMenuMsgIdx(null);
      const isYes = /yes|yeah|yep|sure|show|want/i.test(content);
      const releaseDeferred = () => {
        const d = deferredAiMessageRef.current;
        deferredAiMessageRef.current = null;
        return d ? [d] : [];
      };

      // ── Contact: email ──
      if (frontendStep === 'contact_email') {
        onSlotsUpdate?.({ email: content } as any);
        const phoneMsg: ChatMessage = {
          role: 'ai',
          content: 'And your phone number?',
          timestamp: new Date(),
        };
        setState((prev) => ({ ...prev, messages: [...prev.messages, userMsg, phoneMsg] }));
        setFrontendStep('contact_phone');
        return;
      }

      // ── Contact: phone ──
      if (frontendStep === 'contact_phone') {
        const phone = content.replace(/[^\d+]/g, '');
        onSlotsUpdate?.({ phone } as any);
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, userMsg, ...releaseDeferred()],
        }));
        setFrontendStep(null);
        return;
      }

      // ── Wedding cake: ask ──
      if (frontendStep === 'cake_ask') {
        if (isYes) {
          const flavorMsg: ChatMessage = {
            role: 'ai',
            content: 'Wonderful! Pick a cake flavor:\n1. Yellow\n2. White\n3. Almond\n4. Chocolate\n5. Carrot\n6. Red Velvet\n7. Bananas Foster\n8. Whiskey Caramel\n9. Lemon\n10. Spice\n11. Funfetti\n12. Pumpkin Spice\n13. Cookies and Cream\n14. Strawberry\n15. Coconut',
            timestamp: new Date(),
          };
          setState((prev) => ({ ...prev, messages: [...prev.messages, userMsg, flavorMsg] }));
          setFrontendStep('cake_flavor');
        } else {
          setState((prev) => ({ ...prev, messages: [...prev.messages, userMsg, ...releaseDeferred()] }));
          setFrontendStep(null);
        }
        return;
      }

      // ── Wedding cake: flavor ──
      if (frontendStep === 'cake_flavor') {
        weddingCakeDataRef.current.flavor = content;
        const fillingMsg: ChatMessage = {
          role: 'ai',
          content: 'Great pick! Now choose a filling:\n1. Butter Cream\n2. Lemon Curd\n3. Raspberry Jam\n4. Strawberry Jam\n5. Cream Cheese Icing\n6. Peanut Butter Cream\n7. Mocha Buttercream\n8. Salted Caramel Buttercream\n9. Cinnamon Butter Cream',
          timestamp: new Date(),
        };
        setState((prev) => ({ ...prev, messages: [...prev.messages, userMsg, fillingMsg] }));
        setFrontendStep('cake_filling');
        return;
      }

      // ── Wedding cake: filling ──
      if (frontendStep === 'cake_filling') {
        weddingCakeDataRef.current.filling = content;
        const bcMsg: ChatMessage = {
          role: 'ai',
          content: 'Almost done! Choose your buttercream frosting:\n1. Signature\n2. Chocolate\n3. Cream Cheese Frosting',
          timestamp: new Date(),
        };
        setState((prev) => ({ ...prev, messages: [...prev.messages, userMsg, bcMsg] }));
        setFrontendStep('cake_buttercream');
        return;
      }

      // ── Wedding cake: buttercream (final) ──
      if (frontendStep === 'cake_buttercream') {
        const { flavor, filling } = weddingCakeDataRef.current;
        const summaryMsg: ChatMessage = {
          role: 'ai',
          content: `Wedding cake set! 2 Tier 6" & 8" ($275) — ${flavor} cake, ${filling} filling, ${content} frosting.`,
          timestamp: new Date(),
        };
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, userMsg, summaryMsg, ...releaseDeferred()],
        }));
        onSlotsUpdate?.({ wedding_cake: `2 Tier 6" & 8" — ${flavor}, ${filling}, ${content}` } as any);
        weddingCakeDataRef.current = {};
        setFrontendStep(null);
        return;
      }
    }
    // ─── End frontend-only interception ───────────────────────────────

    if (content.startsWith('/')) {
      const command = content.toLowerCase();
      if (command.startsWith('/menu')) {
        setCommandDialog({ isOpen: true, command: 'menu' });
        setInput('');
        return;
      }
      if (command.startsWith('/event')) {
        setCommandDialog({ isOpen: true, command: 'events' });
        setInput('');
        return;
      }
      if (command.startsWith('/help')) {
        toast.success('Help request sent! Our team will assist you shortly.');
      }
    }

    setInput('');
    setMenuSelections([]);
    setActiveMenuMsgIdx(null);

    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      error: undefined,
    }));

    try {
      const response = await chatAiApi.sendMessageWithRetry({
        message: content,
        threadId: state.threadId,
        projectId,
        authorId,
        userId,
      });

      const aiMessage: ChatMessage = {
        role: 'ai',
        content: response.message,
        timestamp: new Date(),
      };

      // Count real user messages (exclude auto-greeting)
      const userMsgCount = state.messages.filter((m) => m.role === 'user').length + 1; // +1 for current

      // After user gives name (2nd user msg) → inject email+phone questions
      const isNameResponse = !contactAskedRef.current && userMsgCount === 2
        && !content.startsWith('/') && !/\d{5,}/.test(content); // not a phone/number

      // After user selects "Wedding" → inject cake question
      const isWeddingSelection = !weddingCakeAskedRef.current
        && /wedding/i.test(content)
        && !/(venue|guest|date|appetizer|menu|dessert|cake|email|phone)/i.test(content);

      if (isNameResponse) {
        contactAskedRef.current = true;
        deferredAiMessageRef.current = aiMessage;
        const emailAsk: ChatMessage = {
          role: 'ai',
          content: 'What\'s the best email to reach you at?',
          timestamp: new Date(),
        };
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, emailAsk],
          threadId: response.thread_id,
          progress: { filled: response.slots_filled, total: response.total_slots },
          isComplete: response.is_complete,
          isLoading: false,
        }));
        setFrontendStep('contact_email');
      } else if (isWeddingSelection) {
        weddingCakeAskedRef.current = true;
        deferredAiMessageRef.current = aiMessage;
        const cakeAsk: ChatMessage = {
          role: 'ai',
          content: '🎂 Would you like a wedding cake?\n1. Yes\n2. No thanks',
          timestamp: new Date(),
        };
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, cakeAsk],
          threadId: response.thread_id,
          progress: { filled: response.slots_filled, total: response.total_slots },
          isComplete: response.is_complete,
          isLoading: false,
        }));
        setFrontendStep('cake_ask');
      } else {
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, aiMessage],
          threadId: response.thread_id,
          progress: { filled: response.slots_filled, total: response.total_slots },
          isComplete: response.is_complete,
          isLoading: false,
        }));
      }

      onProgressUpdate?.({ filled: response.slots_filled, total: response.total_slots });
      saveSessionToStorage(response.thread_id);
      if (!state.threadId) onThreadStart?.(response.thread_id);

      // Auto-detect email and phone in user messages → save to slots
      const emailMatch = content.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
      if (emailMatch) onSlotsUpdate?.({ email: emailMatch[0] } as any);
      const phoneMatch = content.match(/\+?\d[\d\s()-]{8,}\d/);
      if (phoneMatch) onSlotsUpdate?.({ phone: phoneMatch[0].replace(/[\s()-]/g, '') } as any);

      if (onSlotsUpdate && response.slots_filled > lastSlotsFilled.current) {
        lastSlotsFilled.current = response.slots_filled;
        chatAiApi.getConversation(response.thread_id)
          .then((conv) => { if (conv.slots) onSlotsUpdate(conv.slots); })
          .catch(() => {});
      }

      if (response.is_complete) {
        toast.success('Event details collected! You can now create your project.');
        try {
          const conversation = await chatAiApi.getConversation(response.thread_id);
          const slots = { ...conversation.slots, thread_id: response.thread_id };
          setState((prev) => ({ ...prev, contractData: slots }));
        } catch (err) {
          console.error('Failed to fetch conversation slots:', err);
        }
      }
    } catch (error: any) {
      console.error('Failed to send message:', error);
      setState((prev) => ({ ...prev, isLoading: false, error: 'Failed to send message. Please try again.' }));
      toast.error('Failed to send message');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleCommandSelect = (selectedOption: string) => {
    handleSendMessage(`I'm interested in ${selectedOption}`);
  };

  return (
    <>
      <CommandDialog
        isOpen={commandDialog.isOpen}
        command={commandDialog.command}
        onClose={() => setCommandDialog({ isOpen: false, command: null })}
        onSelect={handleCommandSelect}
      />
      <div className="flex flex-col h-full bg-white">
        {/* Header */}
        <div className="border-b border-neutral-200 px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 bg-black rounded-xl flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-neutral-900">Catering Assistant</h2>
              <p className="text-xs text-neutral-500 hidden sm:block">Let's plan your perfect event together</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 space-y-4">
          {state.messages.map((msg, idx) => {
            const userInitial = userName.charAt(0).toUpperCase();
            const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const isActive = idx === activeMenuMsgIdx;
            const listItems = isActive ? parseListItems(msg.content) : null;
            const categorizedItems = isActive && listItems
              ? (parseCategorizedItems(msg.content) ?? groupItemsByCategory(listItems))
              : null;

            if (msg.role === 'ai' && listItems) {
              const { intro } = splitAtList(msg.content);
              const isConfirm = isConfirmationMessage(intro);

              // Confirmation messages: render as plain read-only list, not interactive cards
              if (isConfirm) {
                return (
                  <div key={idx} className="flex justify-start gap-2.5">
                    <div className="flex flex-col items-center gap-1 shrink-0">
                      <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
                        <Sparkles className="w-3.5 h-3.5 text-white" />
                      </div>
                      <span className="text-[10px] text-neutral-400">AI</span>
                    </div>
                    <div className="max-w-[90%] sm:max-w-[80%] rounded-2xl px-3 sm:px-4 py-3 bg-neutral-100 text-neutral-900">
                      <MarkdownMessage content={msg.content} />
                      <span className="text-xs mt-1 block text-neutral-400">{time}</span>
                    </div>
                  </div>
                );
              }

              const multi = isMultiSelect(listItems);
              // Only cap desserts (items with no prices but exactly the dessert count ≤8)
              const isDesserts = !listItems.some((i) => i.price) && listItems.length <= 8 && listItems.length > 6;
              const maxSelect = isDesserts ? 4 : undefined;

              return (
                <div key={idx} className="flex justify-start gap-2.5">
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
                      <Sparkles className="w-3.5 h-3.5 text-white" />
                    </div>
                    <span className="text-[10px] text-neutral-400">AI</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    {intro && (
                      <div className="rounded-2xl px-4 py-3 bg-neutral-100 text-neutral-900 mb-2 inline-block max-w-[90%]">
                        <MarkdownMessage content={intro} />
                      </div>
                    )}
                    <ItemSelector
                      items={listItems}
                      categories={categorizedItems ?? undefined}
                      selected={menuSelections}
                      onSelectionChange={handleMenuSelectionChange}
                      multi={multi}
                      maxSelect={maxSelect}
                    />
                    <span className="text-xs text-neutral-400 mt-1 block">{time}</span>
                  </div>
                </div>
              );
            }

            if (msg.role === 'user') {
              return (
                <div key={idx} className="flex justify-end gap-2.5">
                  <div className="max-w-[85%] sm:max-w-[80%] rounded-2xl px-3 sm:px-4 py-3 bg-black text-white">
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <span className="text-xs mt-1 block text-neutral-400">{time}</span>
                  </div>
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <div className="w-7 h-7 rounded-full bg-neutral-800 flex items-center justify-center">
                      <span className="text-xs font-bold text-white">{userInitial}</span>
                    </div>
                    <span className="text-[10px] text-neutral-400">You</span>
                  </div>
                </div>
              );
            }

            return (
              <div key={idx} className="flex justify-start gap-2.5">
                <div className="flex flex-col items-center gap-1 shrink-0">
                  <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
                    <Sparkles className="w-3.5 h-3.5 text-white" />
                  </div>
                  <span className="text-[10px] text-neutral-400">AI</span>
                </div>
                <div className="max-w-[90%] sm:max-w-[80%] rounded-2xl px-3 sm:px-4 py-3 bg-neutral-100 text-neutral-900">
                  <MarkdownMessage content={msg.content} />
                  <span className="text-xs mt-1 block text-neutral-400">{time}</span>
                </div>
              </div>
            );
          })}

          {state.isLoading && (
            <div className="flex justify-start">
              <div className="bg-neutral-100 rounded-2xl px-4 py-3">
                <Loader2 className="w-5 h-5 text-neutral-400 animate-spin" />
              </div>
            </div>
          )}

          {state.error && (
            <div className="flex justify-center">
              <div className="bg-red-50 text-red-600 rounded-lg px-4 py-2 text-sm">{state.error}</div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Completion — intake review accordion */}
        {state.isComplete && state.contractData && (
          <IntakeReviewPanel
            contractData={state.contractData}
            onConfirm={() => onComplete?.(state.contractData!)}
          />
        )}

        {/* Input */}
        {(() => {
          const lastAiMsg = [...state.messages].reverse().find((m) => m.role === 'ai');
          const noMenu = activeMenuMsgIdx === null;
          const isPhoneMode = !state.isLoading && !!lastAiMsg && isAskingForPhone(lastAiMsg.content) && noMenu;
          const isEmailMode = !state.isLoading && !!lastAiMsg && isAskingForEmail(lastAiMsg.content) && noMenu && !isPhoneMode;
          const isDateMode = !state.isLoading && !!lastAiMsg && isAskingForDate(lastAiMsg.content) && noMenu && !isPhoneMode && !isEmailMode;
          const specialMode = isPhoneMode || isEmailMode || isDateMode;

          const handleSpecialSend = () => {
            if (isPhoneMode) {
              handleSendMessage(`${countryCode.code} ${input}`);
            } else {
              handleSendMessage();
            }
            setInput('');
          };

          return (
            <div className={`border-t border-neutral-200 px-3 sm:px-6 py-3 sm:py-4 bg-white${state.isComplete && state.contractData ? ' hidden' : ''}`}>
              <div className="flex items-end gap-2 sm:gap-3">
                {isPhoneMode ? (
                  /* Phone input with country code */
                  <div className="flex-1 flex items-center border border-neutral-200 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-black focus-within:border-transparent">
                    <div className="relative shrink-0">
                      <select
                        value={COUNTRY_CODES.indexOf(countryCode)}
                        onChange={(e) => setCountryCode(COUNTRY_CODES[Number(e.target.value)])}
                        className="appearance-none bg-neutral-50 border-r border-neutral-200 pl-3 pr-7 py-3 text-sm text-neutral-700 focus:outline-none cursor-pointer h-full"
                      >
                        {COUNTRY_CODES.map((c, i) => (
                          <option key={`${c.code}-${c.name}`} value={i}>
                            {c.flag} {c.name} {c.code}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
                    </div>
                    <input
                      type="tel"
                      value={input}
                      onChange={(e) => setInput(e.target.value.replace(/[^\d]/g, '').slice(0, 10))}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSpecialSend(); } }}
                      placeholder="0000000000"
                      maxLength={10}
                      className="flex-1 px-3 py-3 text-sm focus:outline-none bg-white"
                      disabled={state.isLoading}
                    />
                  </div>
                ) : isEmailMode ? (
                  /* Email input with validation */
                  <input
                    type="email"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSpecialSend(); } }}
                    placeholder="you@example.com"
                    className="flex-1 border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                    disabled={state.isLoading}
                  />
                ) : isDateMode ? (
                  /* Date picker input */
                  <input
                    type="date"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSpecialSend(); } }}
                    min={new Date().toISOString().split('T')[0]}
                    max={(() => { const d = new Date(); d.setMonth(d.getMonth() + 7); return d.toISOString().split('T')[0]; })()}
                    className="flex-1 border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                    disabled={state.isLoading}
                  />
                ) : (
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      if (activeMenuMsgIdx !== null) setMenuSelections([]);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder={activeMenuMsgIdx !== null ? 'Select items above or type here…' : 'Type your message…'}
                    className="flex-1 resize-none border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent min-h-[52px] max-h-[120px]"
                    rows={1}
                    disabled={state.isLoading}
                  />
                )}
                <button
                  onClick={specialMode ? handleSpecialSend : () => handleSendMessage()}
                  disabled={!input.trim() || state.isLoading || (isEmailMode && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input))}
                  className="bg-black text-white p-3 rounded-xl hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                >
                  {state.isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-neutral-400 mt-2 text-center">
                {isPhoneMode
                  ? 'Select your country code and enter your phone number'
                  : isEmailMode
                    ? 'Enter a valid email address'
                    : isDateMode
                      ? 'Pick your event date'
                      : activeMenuMsgIdx !== null
                        ? 'Click cards to select · Send to confirm'
                        : <>Shift+Enter for new line · Use <span className="font-mono text-neutral-600">@ai</span> to update previous items</>
                }
              </p>
            </div>
          );
        })()}
      </div>
    </>
  );
}
