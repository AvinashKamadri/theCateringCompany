"use client";

import Link from 'next/link';
import { ArrowLeft, UtensilsCrossed, ChevronRight } from 'lucide-react';

const MENU_CATEGORIES = [
  {
    id: 'wedding',
    name: 'Wedding Menu',
    description: 'Elegant dining for your special day',
    image: '🎂',
    items: [
      'Gourmet Appetizers',
      'Premium Entrees',
      'Signature Desserts',
      'Custom Wedding Cake',
    ],
  },
  {
    id: 'corporate',
    name: 'Corporate Events',
    description: 'Professional catering for business',
    image: '💼',
    items: [
      'Continental Breakfast',
      'Working Lunch Boxes',
      'Coffee & Tea Service',
      'Executive Dinner',
    ],
  },
  {
    id: 'casual',
    name: 'Casual Gatherings',
    description: 'Relaxed dining for any occasion',
    image: '🍕',
    items: [
      'BBQ Platters',
      'Finger Foods',
      'Salad Bar',
      'Dessert Station',
    ],
  },
  {
    id: 'formal',
    name: 'Formal Dinners',
    description: 'Sophisticated multi-course dining',
    image: '🍽️',
    items: [
      'French Service',
      'Plated Dinners',
      'Wine Pairings',
      'Chef\'s Tasting Menu',
    ],
  },
];

export default function MenuPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/chat"
              className="text-gray-600 hover:text-gray-900 transition"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Our Menus</h1>
              <p className="text-sm text-gray-600 mt-1">
                Explore our catering options
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {MENU_CATEGORIES.map((category) => (
            <div
              key={category.id}
              className="bg-white rounded-2xl shadow-lg overflow-hidden hover:shadow-xl transition group"
            >
              {/* Card Header */}
              <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-6">
                <div className="flex items-center gap-4">
                  <div className="text-4xl">{category.image}</div>
                  <div className="flex-1">
                    <h2 className="text-xl font-bold text-white">
                      {category.name}
                    </h2>
                    <p className="text-blue-100 text-sm mt-1">
                      {category.description}
                    </p>
                  </div>
                  <ChevronRight className="w-6 h-6 text-white group-hover:translate-x-1 transition" />
                </div>
              </div>

              {/* Card Body */}
              <div className="p-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <UtensilsCrossed className="w-4 h-4" />
                  Popular Items
                </h3>
                <ul className="space-y-2">
                  {category.items.map((item, idx) => (
                    <li
                      key={idx}
                      className="flex items-center gap-2 text-sm text-gray-600"
                    >
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                      {item}
                    </li>
                  ))}
                </ul>

                <Link
                  href={`/chat?menu=${category.id}`}
                  className="mt-6 w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-900 font-medium rounded-lg transition"
                >
                  Discuss this menu
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          ))}
        </div>

        {/* CTA Section */}
        <div className="mt-12 bg-white rounded-2xl shadow-lg p-8 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Need a Custom Menu?
          </h2>
          <p className="text-gray-600 mb-6">
            Our chefs can create a personalized menu tailored to your event
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold rounded-lg hover:from-blue-600 hover:to-purple-700 transition"
          >
            Start Planning Your Event
            <ChevronRight className="w-5 h-5" />
          </Link>
        </div>
      </main>
    </div>
  );
}
