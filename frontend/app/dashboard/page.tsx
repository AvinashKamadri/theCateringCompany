"use client";

import { useState } from "react";

type CateringEvent = {
    id: string;
    title: string;
    desc: string;
    date: string;
    status: "CONFIRMED" | "PENDING" | "DRAFT";
};

const MOCK_EVENTS: CateringEvent[] = [
    { id: "1", title: "Johnson Wedding Reception", desc: "300 guests, 5-course meal, 12 Jun 2026", date: "Mar 1, 2026", status: "CONFIRMED" },
    { id: "2", title: "TechCorp Annual Gala", desc: "Corporate dinner, 150 guests, 20 Jun 2026", date: "Mar 2, 2026", status: "DRAFT" },
    { id: "3", title: "Patel Birthday Feast", desc: "Private garden party, 60 guests, 5 Jul 2026", date: "Mar 5, 2026", status: "PENDING" },
    { id: "4", title: "City Hospital Fundraiser", desc: "Gala dinner, 200 guests, 15 Jul 2026", date: "Mar 6, 2026", status: "CONFIRMED" },
];

const statusColor: Record<string, { bg: string; color: string }> = {
    CONFIRMED: { bg: "#ecfdf5", color: "#059669" },
    PENDING: { bg: "#fffbeb", color: "#d97706" },
    DRAFT: { bg: "#f3f4f6", color: "#6b7280" },
};

export default function EventsPage() {
    const [events] = useState<CateringEvent[]>(MOCK_EVENTS);
    const [showForm, setShowForm] = useState(false);

    const confirmed = events.filter(e => e.status === "CONFIRMED").length;
    const pending = events.filter(e => e.status === "PENDING").length;

    const stats = [
        { icon: "📋", label: "Total Events", value: events.length, color: "#111" },
        { icon: "✅", label: "Confirmed", value: confirmed, color: "#059669" },
        { icon: "⏳", label: "Pending", value: pending, color: "#d97706" },
        { icon: "📅", label: "This Month", value: 3, color: "#2563eb" },
    ];

    return (
        <div style={{ padding: "32px 40px", maxWidth: 900 }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, color: "#111", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{ fontSize: 22 }}>🎉</span> Events
                    </h1>
                    <p style={{ fontSize: 14, color: "#9ca3af", marginTop: 4 }}>Manage all your catering events and bookings</p>
                </div>
                <button onClick={() => setShowForm(!showForm)} style={{
                    padding: "9px 18px", borderRadius: 8, background: "#111",
                    color: "#fff", fontSize: 14, fontWeight: 600, border: "none",
                    cursor: "pointer", fontFamily: "inherit",
                }}>+ New Event</button>
            </div>

            {/* Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 28 }}>
                {stats.map(s => (
                    <div key={s.label} style={{
                        padding: "18px 20px", borderRadius: 12,
                        border: "1px solid #f0f0f0", background: "#fff",
                    }}>
                        <div style={{ fontSize: 18, marginBottom: 8 }}>{s.icon}</div>
                        <div style={{ fontSize: 26, fontWeight: 800, color: s.color, letterSpacing: "-0.02em" }}>{s.value}</div>
                        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>{s.label}</div>
                    </div>
                ))}
            </div>

            {/* New Event Form */}
            {showForm && (
                <div style={{
                    padding: 24, borderRadius: 12, border: "1px solid #f0f0f0",
                    background: "#fff", marginBottom: 20,
                }}>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: "#111", marginBottom: 16 }}>Create New Event</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                        <input placeholder="Event title" style={{ padding: "10px 14px", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 14, fontFamily: "inherit", outline: "none" }} />
                        <input type="date" style={{ padding: "10px 14px", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 14, fontFamily: "inherit", outline: "none" }} />
                    </div>
                    <input placeholder="Description (guests, cuisine type, etc.)" style={{ width: "100%", padding: "10px 14px", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 14, fontFamily: "inherit", outline: "none", boxSizing: "border-box", marginBottom: 12 }} />
                    <button onClick={() => setShowForm(false)} style={{
                        padding: "10px 20px", borderRadius: 8, background: "#111",
                        color: "#fff", fontSize: 14, fontWeight: 600, border: "none",
                        cursor: "pointer", fontFamily: "inherit",
                    }}>Create Event</button>
                </div>
            )}

            {/* Event list */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {events.map(ev => (
                    <div key={ev.id} style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "16px 20px", borderRadius: 12,
                        border: "1px solid #f0f0f0", background: "#fff",
                        cursor: "pointer", transition: "box-shadow 0.15s",
                    }}
                        onMouseOver={e => (e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.04)")}
                        onMouseOut={e => (e.currentTarget.style.boxShadow = "none")}
                    >
                        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                            <div style={{
                                width: 36, height: 36, borderRadius: "50%", background: "#f3f4f6",
                                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
                            }}>🎉</div>
                            <div>
                                <div style={{ fontSize: 14, fontWeight: 600, color: "#111" }}>{ev.title}</div>
                                <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>{ev.desc}</div>
                            </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                            <span style={{ fontSize: 12, color: "#9ca3af" }}>{ev.date}</span>
                            <span style={{
                                fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 999,
                                background: statusColor[ev.status].bg,
                                color: statusColor[ev.status].color,
                                letterSpacing: "0.02em",
                            }}>{ev.status}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
