"use client";

import { useState } from "react";

type Transaction = {
    id: string;
    event: string;
    amount: number;
    status: "PAID" | "PENDING" | "OVERDUE";
    date: string;
    method: string;
};

const MOCK_TXN: Transaction[] = [
    { id: "1", event: "Johnson Wedding Reception", amount: 12500, status: "PAID", date: "Mar 1, 2026", method: "Bank Transfer" },
    { id: "2", event: "TechCorp Annual Gala", amount: 8200, status: "PENDING", date: "Mar 2, 2026", method: "Invoice" },
    { id: "3", event: "Patel Birthday Feast", amount: 3400, status: "PENDING", date: "Mar 5, 2026", method: "Card" },
    { id: "4", event: "City Hospital Fundraiser", amount: 15000, status: "PAID", date: "Mar 6, 2026", method: "Bank Transfer" },
    { id: "5", event: "Williams Anniversary", amount: 4500, status: "OVERDUE", date: "Feb 20, 2026", method: "Invoice" },
];

const statusStyle: Record<string, { bg: string; color: string }> = {
    PAID: { bg: "#ecfdf5", color: "#059669" },
    PENDING: { bg: "#fffbeb", color: "#d97706" },
    OVERDUE: { bg: "#fef2f2", color: "#dc2626" },
};

export default function PaymentsPage() {
    const [txns] = useState(MOCK_TXN);

    const totalRevenue = txns.filter(t => t.status === "PAID").reduce((s, t) => s + t.amount, 0);
    const totalPending = txns.filter(t => t.status === "PENDING").reduce((s, t) => s + t.amount, 0);
    const totalOverdue = txns.filter(t => t.status === "OVERDUE").reduce((s, t) => s + t.amount, 0);

    const stats = [
        { icon: "💰", label: "Total Revenue", value: `£${totalRevenue.toLocaleString()}`, color: "#059669" },
        { icon: "⏳", label: "Pending", value: `£${totalPending.toLocaleString()}`, color: "#d97706" },
        { icon: "⚠️", label: "Overdue", value: `£${totalOverdue.toLocaleString()}`, color: "#dc2626" },
        { icon: "📄", label: "Invoices Sent", value: txns.length.toString(), color: "#111" },
    ];

    return (
        <div style={{ padding: "32px 40px", maxWidth: 900 }}>
            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, color: "#111", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{ fontSize: 22 }}>💳</span> Payments
                    </h1>
                    <p style={{ fontSize: 14, color: "#9ca3af", marginTop: 4 }}>Track invoices, deposits and balances</p>
                </div>
                <button style={{
                    padding: "9px 18px", borderRadius: 8, background: "#111",
                    color: "#fff", fontSize: 14, fontWeight: 600, border: "none",
                    cursor: "pointer", fontFamily: "inherit",
                }}>+ New Invoice</button>
            </div>

            {/* Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 28 }}>
                {stats.map(s => (
                    <div key={s.label} style={{ padding: "18px 20px", borderRadius: 12, border: "1px solid #f0f0f0", background: "#fff" }}>
                        <div style={{ fontSize: 18, marginBottom: 8 }}>{s.icon}</div>
                        <div style={{ fontSize: 22, fontWeight: 800, color: s.color, letterSpacing: "-0.02em" }}>{s.value}</div>
                        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>{s.label}</div>
                    </div>
                ))}
            </div>

            {/* Table */}
            <div style={{ borderRadius: 12, border: "1px solid #f0f0f0", background: "#fff", overflow: "hidden" }}>
                {/* Header row */}
                <div style={{
                    display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                    padding: "12px 20px", borderBottom: "1px solid #f0f0f0",
                    fontSize: 11, fontWeight: 700, color: "#9ca3af",
                    letterSpacing: "0.05em", textTransform: "uppercase",
                }}>
                    <span>Event</span>
                    <span>Date</span>
                    <span>Amount</span>
                    <span>Method</span>
                    <span style={{ textAlign: "right" }}>Status</span>
                </div>

                {txns.map((t, i) => (
                    <div key={t.id} style={{
                        display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                        padding: "14px 20px", alignItems: "center",
                        borderBottom: i < txns.length - 1 ? "1px solid #f8f8f8" : "none",
                        transition: "background 0.1s",
                    }}
                        onMouseOver={e => (e.currentTarget.style.background = "#fafafa")}
                        onMouseOut={e => (e.currentTarget.style.background = "transparent")}
                    >
                        <span style={{ fontSize: 14, fontWeight: 500, color: "#111" }}>{t.event}</span>
                        <span style={{ fontSize: 13, color: "#9ca3af" }}>{t.date}</span>
                        <span style={{ fontSize: 14, fontWeight: 600, color: "#111" }}>£{t.amount.toLocaleString()}</span>
                        <span style={{ fontSize: 13, color: "#6b7280" }}>{t.method}</span>
                        <span style={{ textAlign: "right" }}>
                            <span style={{
                                fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 999,
                                background: statusStyle[t.status].bg,
                                color: statusStyle[t.status].color,
                            }}>{t.status}</span>
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
