"use client";

import { useState } from "react";

type MenuItem = {
    id: string;
    name: string;
    category: string;
    price: number;
    dietary: string[];
    desc: string;
};

const MOCK_ITEMS: MenuItem[] = [
    { id: "1", name: "Herb-Crusted Salmon", category: "Main", price: 32, dietary: ["GF"], desc: "Atlantic salmon, herb crust, seasonal vegetables" },
    { id: "2", name: "Truffle Risotto", category: "Main", price: 28, dietary: ["V"], desc: "Arborio rice, black truffle, parmesan" },
    { id: "3", name: "Bruschetta Trio", category: "Starter", price: 14, dietary: ["V"], desc: "Tomato basil, mushroom, goat cheese" },
    { id: "4", name: "Prawn Cocktail", category: "Starter", price: 16, dietary: ["GF"], desc: "Tiger prawns, Marie Rose sauce, lettuce" },
    { id: "5", name: "Tiramisu", category: "Dessert", price: 12, dietary: ["V"], desc: "Mascarpone, espresso, cocoa dusted" },
    { id: "6", name: "Crème Brûlée", category: "Dessert", price: 11, dietary: ["V", "GF"], desc: "Vanilla custard, caramelised sugar" },
    { id: "7", name: "Classic Mojito", category: "Drinks", price: 9, dietary: ["V", "GF"], desc: "Rum, mint, lime, soda water" },
    { id: "8", name: "Sparkling Elderflower", category: "Drinks", price: 6, dietary: ["V", "GF"], desc: "Non-alcoholic elderflower pressé" },
];

const CATEGORIES = ["All", "Starter", "Main", "Dessert", "Drinks"];

const dietaryColor: Record<string, { bg: string; color: string }> = {
    V: { bg: "#ecfdf5", color: "#059669" },
    GF: { bg: "#eff6ff", color: "#2563eb" },
    VG: { bg: "#faf5ff", color: "#7c3aed" },
};

export default function FoodPage() {
    const [filter, setFilter] = useState("All");
    const [showForm, setShowForm] = useState(false);

    const filtered = filter === "All" ? MOCK_ITEMS : MOCK_ITEMS.filter(i => i.category === filter);

    return (
        <div style={{ padding: "32px 40px", maxWidth: 900 }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, color: "#111", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{ fontSize: 22 }}>🍽️</span> Food & Menu
                    </h1>
                    <p style={{ fontSize: 14, color: "#9ca3af", marginTop: 4 }}>Build and manage your catering menus</p>
                </div>
                <button onClick={() => setShowForm(!showForm)} style={{
                    padding: "9px 18px", borderRadius: 8, background: "#111",
                    color: "#fff", fontSize: 14, fontWeight: 600, border: "none",
                    cursor: "pointer", fontFamily: "inherit",
                }}>+ Add Item</button>
            </div>

            {/* Category filter pills */}
            <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
                {CATEGORIES.map(c => (
                    <button key={c} onClick={() => setFilter(c)} style={{
                        padding: "6px 16px", borderRadius: 999, fontSize: 13, fontWeight: 500,
                        border: filter === c ? "none" : "1px solid #e5e7eb",
                        background: filter === c ? "#111" : "#fff",
                        color: filter === c ? "#fff" : "#6b7280",
                        cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
                    }}>{c}</button>
                ))}
            </div>

            {/* Add item form */}
            {showForm && (
                <div style={{ padding: 24, borderRadius: 12, border: "1px solid #f0f0f0", background: "#fff", marginBottom: 20 }}>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: "#111", marginBottom: 16 }}>Add Menu Item</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                        <input placeholder="Item name" style={{ padding: "10px 14px", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 14, fontFamily: "inherit", outline: "none" }} />
                        <select style={{ padding: "10px 14px", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 14, fontFamily: "inherit", outline: "none", background: "#fff" }}>
                            {CATEGORIES.filter(c => c !== "All").map(c => <option key={c}>{c}</option>)}
                        </select>
                    </div>
                    <input placeholder="Description" style={{ width: "100%", padding: "10px 14px", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 14, fontFamily: "inherit", outline: "none", boxSizing: "border-box", marginBottom: 12 }} />
                    <button onClick={() => setShowForm(false)} style={{
                        padding: "10px 20px", borderRadius: 8, background: "#111", color: "#fff",
                        fontSize: 14, fontWeight: 600, border: "none", cursor: "pointer", fontFamily: "inherit",
                    }}>Add Item</button>
                </div>
            )}

            {/* Menu grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
                {filtered.map(item => (
                    <div key={item.id} style={{
                        padding: 20, borderRadius: 12, border: "1px solid #f0f0f0",
                        background: "#fff", transition: "box-shadow 0.15s", cursor: "pointer",
                    }}
                        onMouseOver={e => (e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.04)")}
                        onMouseOut={e => (e.currentTarget.style.boxShadow = "none")}
                    >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                            <div style={{ fontSize: 15, fontWeight: 600, color: "#111" }}>{item.name}</div>
                            <div style={{ fontSize: 15, fontWeight: 700, color: "#111" }}>£{item.price}</div>
                        </div>
                        <div style={{ fontSize: 13, color: "#9ca3af", marginBottom: 10, lineHeight: 1.5 }}>{item.desc}</div>
                        <div style={{ display: "flex", gap: 6 }}>
                            <span style={{
                                fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999,
                                background: "#f3f4f6", color: "#6b7280",
                            }}>{item.category}</span>
                            {item.dietary.map(d => (
                                <span key={d} style={{
                                    fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999,
                                    background: dietaryColor[d]?.bg || "#f3f4f6",
                                    color: dietaryColor[d]?.color || "#6b7280",
                                }}>{d}</span>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
