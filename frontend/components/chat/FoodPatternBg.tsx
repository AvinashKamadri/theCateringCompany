"use client";

/* Tiled food-icon background — no external images, pure SVG paths */

const ICONS = [
  /* 01 Chef hat */
  `<path d="M12 4a5 5 0 0 1 4.9 4H20a3 3 0 0 1 0 6H4a3 3 0 0 1 0-6h3.1A5 5 0 0 1 12 4z" stroke-width="1.5" fill="none"/>
   <rect x="5" y="14" width="14" height="3.5" rx="1" stroke-width="1.5" fill="none"/>`,

  /* Whisk */
  `<line x1="12" y1="13" x2="12" y2="22" stroke-width="1.8"/>
   <path d="M8 5 Q10 10 12 13 Q14 10 16 5" stroke-width="1.5" fill="none"/>
   <path d="M9 3 Q12 8 12 8 Q12 8 15 3" stroke-width="1.4" fill="none"/>
   <ellipse cx="12" cy="3.5" rx="3.5" ry="1.3" stroke-width="1.3" fill="none"/>
   <line x1="8" y1="8" x2="16" y2="8" stroke-width="1.1"/>`,

  /* Mixing bowl */
  `<path d="M3 9 Q3 19 12 19 Q21 19 21 9Z" stroke-width="1.6" fill="none"/>
   <line x1="2" y1="9" x2="22" y2="9" stroke-width="1.6"/>
   <line x1="9" y1="19.5" x2="15" y2="21" stroke-width="1.4"/>
   <path d="M7 13 Q12 16 17 13" stroke-width="1.1" fill="none"/>`,

  /* Oven mitt */
  `<path d="M8 21 L8 11 Q8 6 11 6 Q13 6 13 10 L13 13 Q15.5 10.5 17 11.5 Q18.5 12.5 17.5 15 Q19 15.5 18.5 18 Q19.5 18.5 18.5 21Z" stroke-width="1.5" fill="none"/>
   <line x1="8" y1="17.5" x2="18.5" y2="17.5" stroke-width="1.1"/>
   <line x1="13" y1="14" x2="17.5" y2="14.5" stroke-width="1.1"/>
   <path d="M6 21 L20 21" stroke-width="1.8"/>`,

  /* Ice cream cone */
  `<path d="M9 14 L12 22 L15 14Z" stroke-width="1.5" fill="none"/>
   <circle cx="12" cy="10" r="4.5" stroke-width="1.5" fill="none"/>
   <path d="M7.5 13.5 Q12 12 16.5 13.5" stroke-width="1.1" fill="none"/>
   <path d="M9 8 Q11 6 13 8" stroke-width="1.1" fill="none"/>`,

  /* Milk bottle */
  `<path d="M9 3 L9 6 Q6 8 6 11 L6 20 Q6 22 8 22 L16 22 Q18 22 18 20 L18 11 Q18 8 15 6 L15 3Z" stroke-width="1.5" fill="none"/>
   <line x1="9" y1="3" x2="15" y2="3" stroke-width="1.5"/>
   <path d="M6 13.5 Q12 15.5 18 13.5" stroke-width="1.1" fill="none"/>
   <circle cx="12" cy="9" r="1.2" stroke-width="1.1" fill="none"/>`,

  /* Cupcake */
  `<path d="M7 14 Q8 22 12 22 Q16 22 17 14Z" stroke-width="1.5" fill="none"/>
   <path d="M6 14 Q9 7 12 9.5 Q15 7 18 14Z" stroke-width="1.5" fill="none"/>
   <path d="M10 9.5 Q12 4 14 9.5" stroke-width="1.4" fill="none"/>
   <circle cx="12" cy="4" r="1.2" stroke-width="1.2" fill="none"/>`,

  /* Cinnamon roll */
  `<circle cx="12" cy="11" r="7" stroke-width="1.5" fill="none"/>
   <path d="M12 11 m-5 0 a5 5 0 0 1 5-5 a5 5 0 0 1 5 5 a4 4 0 0 1-4 4 a3 3 0 0 1-3-3 a2 2 0 0 1 2-2 a1 1 0 0 1 1 1" stroke-width="1.2" fill="none"/>`,

  /* Egg cracked */
  `<path d="M12 3 Q20 3 20 12 Q20 19 12 19 Q4 19 4 12 Q4 3 12 3Z" stroke-width="1.5" fill="none"/>
   <path d="M8 11 L10.5 13 L13 9.5 L15.5 12" stroke-width="1.4" fill="none"/>`,

  /* Spatula */
  `<line x1="12" y1="2" x2="12" y2="22" stroke-width="1.8"/>
   <rect x="8" y="2" width="8" height="6" rx="2" stroke-width="1.5" fill="none"/>
   <line x1="9" y1="5" x2="15" y2="5" stroke-width="1.1"/>
   <line x1="10" y1="15" x2="14" y2="15" stroke-width="1.1"/>`,

  /* Ladle / spoon */
  `<circle cx="9" cy="7" r="4.5" stroke-width="1.5" fill="none"/>
   <line x1="13" y1="10.5" x2="21" y2="21" stroke-width="1.8"/>
   <path d="M7 5 Q9 3 11 5" stroke-width="1.1" fill="none"/>`,

  /* Yogurt cup */
  `<path d="M7 5 L5 21 Q5 22 6.5 22 L17.5 22 Q19 22 19 21 L17 5Z" stroke-width="1.5" fill="none"/>
   <line x1="7" y1="5" x2="17" y2="5" stroke-width="1.5"/>
   <path d="M9 13 Q12 15.5 15 13" stroke-width="1.2" fill="none"/>
   <circle cx="12" cy="10" r="1.8" stroke-width="1.2" fill="none"/>`,

  /* Croissant */
  `<path d="M4 14 Q5 5 12 7.5 Q19 5 20 14 Q17 19 12 17 Q7 19 4 14Z" stroke-width="1.5" fill="none"/>
   <path d="M7.5 9 Q12 13.5 16.5 9" stroke-width="1.2" fill="none"/>
   <path d="M9 7 Q12 11 15 7" stroke-width="1.0" fill="none"/>`,

  /* Rolling pin */
  `<rect x="4" y="10" width="16" height="4" rx="2" stroke-width="1.5" fill="none"/>
   <line x1="2" y1="12" x2="4" y2="12" stroke-width="2.2"/>
   <line x1="20" y1="12" x2="22" y2="12" stroke-width="2.2"/>
   <line x1="8" y1="10" x2="8" y2="14" stroke-width="1.1"/>
   <line x1="12" y1="10" x2="12" y2="14" stroke-width="1.1"/>
   <line x1="16" y1="10" x2="16" y2="14" stroke-width="1.1"/>`,

  /* Fork */
  `<line x1="12" y1="2" x2="12" y2="22" stroke-width="1.8"/>
   <line x1="9" y1="2" x2="9" y2="8" stroke-width="1.5"/>
   <line x1="15" y1="2" x2="15" y2="8" stroke-width="1.5"/>
   <path d="M9 8 Q12 10 15 8" stroke-width="1.4" fill="none"/>`,

  /* Knife */
  `<line x1="12" y1="3" x2="12" y2="22" stroke-width="1.8"/>
   <path d="M12 3 Q18 6 17 14 L12 14Z" stroke-width="1.4" fill="none"/>`,

  /* Pizza slice */
  `<path d="M12 3 L3 20 Q3 21 4 21 L20 21 Q21 21 21 20 Z" stroke-width="1.5" fill="none"/>
   <circle cx="10" cy="13" r="1.5" stroke-width="1.2" fill="none"/>
   <circle cx="14" cy="16" r="1.2" stroke-width="1.2" fill="none"/>
   <circle cx="12" cy="10" r="1.0" stroke-width="1.1" fill="none"/>`,

  /* Pot / saucepan */
  `<path d="M5 10 Q5 20 12 20 Q19 20 19 10Z" stroke-width="1.5" fill="none"/>
   <line x1="4" y1="10" x2="20" y2="10" stroke-width="1.6"/>
   <line x1="1" y1="11" x2="5" y2="13" stroke-width="1.8"/>
   <line x1="23" y1="11" x2="19" y2="13" stroke-width="1.8"/>
   <rect x="10" y="5" width="4" height="5" rx="1" stroke-width="1.4" fill="none"/>`,

  /* Star / cookie cutter */
  `<polygon points="12,2 14.5,9 22,9 16,14 18.5,21 12,17 5.5,21 8,14 2,9 9.5,9" stroke-width="1.4" fill="none"/>`,

  /* Mug / coffee */
  `<path d="M5 6 L5 19 Q5 21 7 21 L17 21 Q19 21 19 19 L19 6Z" stroke-width="1.5" fill="none"/>
   <line x1="5" y1="6" x2="19" y2="6" stroke-width="1.5"/>
   <path d="M19 9 Q23 9 23 12 Q23 15 19 15" stroke-width="1.5" fill="none"/>
   <path d="M9 2 Q9 4 10 5" stroke-width="1.3" fill="none"/>
   <path d="M13 2 Q13 4 14 5" stroke-width="1.3" fill="none"/>`,

  /* Donut */
  `<circle cx="12" cy="12" r="8" stroke-width="1.5" fill="none"/>
   <circle cx="12" cy="12" r="3.5" stroke-width="1.5" fill="none"/>
   <path d="M6 8 Q8 5 12 4" stroke-width="1.1" fill="none"/>`,

  /* Carrot */
  `<path d="M12 4 Q15 8 15 14 Q15 20 12 21 Q9 20 9 14 Q9 8 12 4Z" stroke-width="1.5" fill="none"/>
   <path d="M12 4 Q10 1 8 2" stroke-width="1.3" fill="none"/>
   <path d="M12 4 Q12 1 11 0" stroke-width="1.3" fill="none"/>
   <path d="M12 4 Q14 1 16 2" stroke-width="1.3" fill="none"/>
   <line x1="10" y1="10" x2="14" y2="10" stroke-width="1.1"/>
   <line x1="9.5" y1="14" x2="14.5" y2="14" stroke-width="1.1"/>`,

  /* 24 Cake / birthday */
  `<rect x="4" y="12" width="16" height="9" rx="1.5" stroke-width="1.5" fill="none"/>
   <line x1="4" y1="16" x2="20" y2="16" stroke-width="1.1"/>
   <line x1="8" y1="12" x2="8" y2="21" stroke-width="1.1"/>
   <line x1="16" y1="12" x2="16" y2="21" stroke-width="1.1"/>
   <line x1="8" y1="9" x2="8" y2="12" stroke-width="1.4"/>
   <line x1="12" y1="8" x2="12" y2="12" stroke-width="1.4"/>
   <line x1="16" y1="9" x2="16" y2="12" stroke-width="1.4"/>
   <circle cx="8" cy="8.5" r="1.2" stroke-width="1.2" fill="none"/>
   <circle cx="12" cy="7.5" r="1.2" stroke-width="1.2" fill="none"/>
   <circle cx="16" cy="8.5" r="1.2" stroke-width="1.2" fill="none"/>`,

  /* 25 Chopsticks */
  `<line x1="8" y1="2" x2="14" y2="22" stroke-width="1.6"/>
   <line x1="16" y1="2" x2="10" y2="22" stroke-width="1.6"/>`,

  /* 26 Frying pan */
  `<circle cx="11" cy="12" r="7" stroke-width="1.5" fill="none"/>
   <line x1="18" y1="12" x2="23" y2="9" stroke-width="2"/>
   <path d="M7 8 Q11 6 15 8" stroke-width="1.1" fill="none"/>`,

  /* 27 Grater / cheese grater */
  `<rect x="7" y="3" width="10" height="18" rx="2" stroke-width="1.5" fill="none"/>
   <circle cx="10" cy="8" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="14" cy="8" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="10" cy="12" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="14" cy="12" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="10" cy="16" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="14" cy="16" r="0.8" stroke-width="1.2" fill="none"/>`,

  /* 28 Blender */
  `<path d="M8 3 L7 14 Q7 16 9 16 L15 16 Q17 16 17 14 L16 3Z" stroke-width="1.5" fill="none"/>
   <rect x="9" y="16" width="6" height="5" rx="1" stroke-width="1.5" fill="none"/>
   <line x1="8" y1="3" x2="16" y2="3" stroke-width="1.5"/>
   <path d="M9 8 L15 10" stroke-width="1.2"/>
   <path d="M9 11 L15 13" stroke-width="1.2"/>`,

  /* 29 Tongs */
  `<path d="M9 3 Q9 12 12 18" stroke-width="1.6" fill="none"/>
   <path d="M15 3 Q15 12 12 18" stroke-width="1.6" fill="none"/>
   <path d="M9 3 Q12 5 15 3" stroke-width="1.4" fill="none"/>
   <path d="M10 18 Q12 21 14 18" stroke-width="1.4" fill="none"/>`,

  /* 30 Measuring cup */
  `<path d="M6 5 L4 20 Q4 22 6 22 L18 22 Q20 22 20 20 L18 5Z" stroke-width="1.5" fill="none"/>
   <line x1="6" y1="5" x2="18" y2="5" stroke-width="1.5"/>
   <line x1="18" y1="10" x2="21" y2="10" stroke-width="1.3"/>
   <line x1="19" y1="15" x2="22" y2="15" stroke-width="1.3"/>
   <line x1="8" y1="10" x2="10" y2="10" stroke-width="1.1"/>
   <line x1="8" y1="15" x2="10" y2="15" stroke-width="1.1"/>`,

  /* 31 Bread loaf */
  `<path d="M4 13 Q4 7 12 7 Q20 7 20 13 L20 20 Q20 21 19 21 L5 21 Q4 21 4 20 Z" stroke-width="1.5" fill="none"/>
   <path d="M4 13 Q12 11 20 13" stroke-width="1.2" fill="none"/>
   <line x1="8" y1="21" x2="8" y2="16" stroke-width="1.1"/>
   <line x1="12" y1="21" x2="12" y2="15" stroke-width="1.1"/>
   <line x1="16" y1="21" x2="16" y2="16" stroke-width="1.1"/>`,

  /* 32 Wine glass */
  `<path d="M8 3 Q6 10 12 14 Q18 10 16 3Z" stroke-width="1.5" fill="none"/>
   <line x1="12" y1="14" x2="12" y2="20" stroke-width="1.8"/>
   <line x1="8" y1="20" x2="16" y2="20" stroke-width="1.8"/>
   <line x1="8" y1="3" x2="16" y2="3" stroke-width="1.3"/>`,

  /* 33 Cocktail / martini */
  `<path d="M4 3 L12 14 L20 3Z" stroke-width="1.5" fill="none"/>
   <line x1="12" y1="14" x2="12" y2="21" stroke-width="1.8"/>
   <line x1="8" y1="21" x2="16" y2="21" stroke-width="1.8"/>
   <circle cx="17" cy="5" r="2" stroke-width="1.2" fill="none"/>`,

  /* 34 Teapot */
  `<path d="M7 8 Q7 19 12 19 Q17 19 17 8Z" stroke-width="1.5" fill="none"/>
   <path d="M17 11 Q21 10 21 13 Q21 16 17 15" stroke-width="1.4" fill="none"/>
   <path d="M9 8 Q12 5 15 8" stroke-width="1.3" fill="none"/>
   <line x1="10" y1="5" x2="10" y2="8" stroke-width="1.4"/>
   <line x1="7" y1="8" x2="17" y2="8" stroke-width="1.5"/>`,

  /* 35 Colander / strainer */
  `<path d="M4 10 Q4 19 12 19 Q20 19 20 10Z" stroke-width="1.5" fill="none"/>
   <line x1="3" y1="10" x2="21" y2="10" stroke-width="1.6"/>
   <circle cx="9" cy="14" r="0.9" stroke-width="1.2" fill="none"/>
   <circle cx="12" cy="14" r="0.9" stroke-width="1.2" fill="none"/>
   <circle cx="15" cy="14" r="0.9" stroke-width="1.2" fill="none"/>
   <circle cx="10.5" cy="17" r="0.9" stroke-width="1.2" fill="none"/>
   <circle cx="13.5" cy="17" r="0.9" stroke-width="1.2" fill="none"/>
   <line x1="3" y1="10" x2="1" y2="12" stroke-width="1.5"/>
   <line x1="21" y1="10" x2="23" y2="12" stroke-width="1.5"/>`,

  /* 36 Pepper mill */
  `<ellipse cx="12" cy="6" rx="4" ry="3" stroke-width="1.5" fill="none"/>
   <path d="M8 9 Q7 18 9 21 L15 21 Q17 18 16 9Z" stroke-width="1.5" fill="none"/>
   <line x1="10" y1="13" x2="14" y2="13" stroke-width="1.1"/>
   <line x1="10" y1="16" x2="14" y2="16" stroke-width="1.1"/>`,

  /* 37 Waffle */
  `<rect x="4" y="4" width="16" height="16" rx="2.5" stroke-width="1.5" fill="none"/>
   <line x1="4" y1="8.5" x2="20" y2="8.5" stroke-width="1.1"/>
   <line x1="4" y1="12" x2="20" y2="12" stroke-width="1.1"/>
   <line x1="4" y1="15.5" x2="20" y2="15.5" stroke-width="1.1"/>
   <line x1="8.5" y1="4" x2="8.5" y2="20" stroke-width="1.1"/>
   <line x1="12" y1="4" x2="12" y2="20" stroke-width="1.1"/>
   <line x1="15.5" y1="4" x2="15.5" y2="20" stroke-width="1.1"/>`,

  /* 38 Lemon / citrus */
  `<ellipse cx="12" cy="12" rx="7" ry="9" stroke-width="1.5" fill="none"/>
   <path d="M5 12 Q12 10 19 12" stroke-width="1.1" fill="none"/>
   <path d="M6 8 Q12 6 18 8" stroke-width="1.0" fill="none"/>
   <path d="M6 16 Q12 18 18 16" stroke-width="1.0" fill="none"/>
   <path d="M12 3 Q14 1 15 2" stroke-width="1.3" fill="none"/>`,

  /* 39 Shrimp / prawn */
  `<path d="M6 18 Q4 12 8 8 Q12 4 16 6 Q20 8 18 13 Q16 17 12 18 Q10 19 9 17 Q11 14 14 14 Q17 14 16 11 Q15 8 12 8 Q9 8 8 11 Q7 14 9 18Z" stroke-width="1.4" fill="none"/>
   <line x1="6" y1="18" x2="4" y2="21" stroke-width="1.3"/>
   <line x1="18" y1="6" x2="20" y2="4" stroke-width="1.3"/>`,

  /* 40 Burger */
  `<path d="M5 13 Q5 10 12 10 Q19 10 19 13Z" stroke-width="1.5" fill="none"/>
   <rect x="4" y="13" width="16" height="3.5" rx="0.5" stroke-width="1.3" fill="none"/>
   <path d="M4 16.5 Q4 20 7 20 L17 20 Q20 20 20 16.5" stroke-width="1.5" fill="none"/>
   <path d="M6 13 Q9 11 12 12 Q15 11 18 13" stroke-width="1.1" fill="none"/>`,

  /* 41 Sushi roll */
  `<circle cx="12" cy="12" r="8" stroke-width="1.5" fill="none"/>
   <circle cx="12" cy="12" r="5" stroke-width="1.2" fill="none"/>
   <circle cx="12" cy="12" r="2" stroke-width="1.2" fill="none"/>
   <path d="M7 7 Q12 5 17 7" stroke-width="1.0" fill="none"/>`,

  /* 42 Avocado */
  `<path d="M12 3 Q17 5 17 13 Q17 20 12 21 Q7 20 7 13 Q7 5 12 3Z" stroke-width="1.5" fill="none"/>
   <circle cx="12" cy="14" r="3.5" stroke-width="1.3" fill="none"/>`,

  /* 43 Mushroom */
  `<path d="M5 12 Q5 5 12 5 Q19 5 19 12Z" stroke-width="1.5" fill="none"/>
   <path d="M8 12 L8 18 Q8 20 10 20 L14 20 Q16 20 16 18 L16 12" stroke-width="1.5" fill="none"/>
   <circle cx="9" cy="9" r="1.2" stroke-width="1.2" fill="none"/>
   <circle cx="14" cy="8" r="1.0" stroke-width="1.1" fill="none"/>`,

  /* 44 Strawberry */
  `<path d="M12 21 Q6 15 6 10 Q6 5 12 4 Q18 5 18 10 Q18 15 12 21Z" stroke-width="1.5" fill="none"/>
   <path d="M10 4 Q9 1 11 2" stroke-width="1.3" fill="none"/>
   <path d="M12 4 Q12 1 13 2" stroke-width="1.3" fill="none"/>
   <path d="M14 4 Q15 1 13.5 2" stroke-width="1.3" fill="none"/>
   <circle cx="10" cy="11" r="0.9" stroke-width="1.1" fill="none"/>
   <circle cx="14" cy="10" r="0.9" stroke-width="1.1" fill="none"/>
   <circle cx="12" cy="15" r="0.9" stroke-width="1.1" fill="none"/>`,

  /* 45 Salt shaker */
  `<path d="M9 7 Q9 3 12 3 Q15 3 15 7 L16 20 Q16 22 12 22 Q8 22 8 20Z" stroke-width="1.5" fill="none"/>
   <line x1="9" y1="7" x2="15" y2="7" stroke-width="1.4"/>
   <circle cx="11" cy="11" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="13" cy="11" r="0.8" stroke-width="1.2" fill="none"/>
   <circle cx="12" cy="13.5" r="0.8" stroke-width="1.2" fill="none"/>`,

  /* 46 Fried egg (sunny side up) */
  `<ellipse cx="12" cy="14" rx="8" ry="6" stroke-width="1.5" fill="none"/>
   <circle cx="12" cy="13" r="3" stroke-width="1.3" fill="none"/>`,

  /* 47 Saucepan side view */
  `<rect x="5" y="8" width="14" height="12" rx="2" stroke-width="1.5" fill="none"/>
   <line x1="5" y1="8" x2="19" y2="8" stroke-width="1.5"/>
   <line x1="19" y1="11" x2="23" y2="10" stroke-width="2"/>
   <rect x="10" y="4" width="4" height="4" rx="1" stroke-width="1.4" fill="none"/>`,

  /* 48 Pineapple */
  `<path d="M12 9 Q7 9 7 15 Q7 21 12 22 Q17 21 17 15 Q17 9 12 9Z" stroke-width="1.5" fill="none"/>
   <path d="M9 9 Q12 3 15 9" stroke-width="1.4" fill="none"/>
   <path d="M10 4 Q11 1 12 3" stroke-width="1.3" fill="none"/>
   <path d="M12 3 Q13 1 14 4" stroke-width="1.3" fill="none"/>
   <path d="M8 12 Q12 14 16 12" stroke-width="1.1" fill="none"/>
   <path d="M8 16 Q12 18 16 16" stroke-width="1.1" fill="none"/>
   <line x1="12" y1="9" x2="12" y2="22" stroke-width="1.0"/>`,

  /* 49 Macaron */
  `<ellipse cx="12" cy="9" rx="7" ry="4" stroke-width="1.5" fill="none"/>
   <ellipse cx="12" cy="15" rx="7" ry="4" stroke-width="1.5" fill="none"/>
   <line x1="5" y1="12" x2="19" y2="12" stroke-width="1.2"/>
   <path d="M6 10 Q12 12 18 10" stroke-width="1.0" fill="none"/>`,

  /* 50 Cocktail glass with straw */
  `<path d="M5 4 L12 14 L19 4Z" stroke-width="1.5" fill="none"/>
   <line x1="5" y1="4" x2="19" y2="4" stroke-width="1.3"/>
   <line x1="12" y1="14" x2="12" y2="21" stroke-width="1.8"/>
   <line x1="8" y1="21" x2="16" y2="21" stroke-width="1.8"/>
   <line x1="15" y1="6" x2="18" y2="16" stroke-width="1.3"/>`,
];

function seededRand(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

export default function FoodPatternBg({
  className = '',
  cols = 9,
  rows = 14,
  opacity = 0.13,
}: {
  className?: string;
  cols?: number;
  rows?: number;
  opacity?: number;
}) {
  const rand = seededRand(137);
  const cellW = 100 / cols;
  const cellH = 100 / rows;

  const items = Array.from({ length: cols * rows }, (_, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const iconIdx = (i * 7 + row * 3) % ICONS.length;
    const icon = ICONS[iconIdx];
    const jx = (rand() - 0.5) * cellW * 0.7;
    const jy = (rand() - 0.5) * cellH * 0.7;
    const rotate = (rand() - 0.5) * 80;
    const scale = 0.044 + rand() * 0.016;
    const cx = cellW * col + cellW / 2 + jx;
    const cy = cellH * row + cellH / 2 + jy;
    return { icon, cx, cy, rotate, scale };
  });

  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`} aria-hidden="true">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="100%"
        height="100%"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
        style={{ position: 'absolute', inset: 0 }}
      >
        <defs>
          <style>{`.food-icon{stroke:#111;fill:none;opacity:${opacity};stroke-linecap:round;stroke-linejoin:round}`}</style>
        </defs>
        {items.map(({ icon, cx, cy, rotate, scale }, i) => (
          <g
            key={i}
            className="food-icon"
            transform={`translate(${cx},${cy}) rotate(${rotate}) scale(${scale}) translate(-12,-12)`}
            dangerouslySetInnerHTML={{ __html: icon }}
          />
        ))}
      </svg>
    </div>
  );
}
