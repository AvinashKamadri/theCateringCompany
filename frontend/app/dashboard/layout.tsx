"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode } from "react";

const NAV_ITEMS = [
    { href: "/dashboard", label: "Events", icon: "📅" },
    { href: "/dashboard/food", label: "Food & Menu", icon: "🍽️" },
    { href: "/dashboard/payments", label: "Payments", icon: "💳" },
];

const QUICK_ACTIONS = [
    { icon: "◇", label: "Collaborations" },
    { icon: "⊞", label: "View Menus" },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();

    return (
        <div style={{ display: "flex", minHeight: "100vh", fontFamily: "'Inter', 'Segoe UI', sans-serif", background: "#f9fafb" }}>
            {/* Sidebar */}
            <aside style={{
                width: 220, background: "#fff", borderRight: "1px solid #f0f0f0",
                display: "flex", flexDirection: "column", flexShrink: 0,
            }}>
                {/* Logo — text only, no icon */}
                <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid #f0f0f0" }}>
                    <Link href="/" style={{ textDecoration: "none" }}>
                        <span style={{ fontSize: 15, fontWeight: 700, color: "#111" }}>The Catering Company</span>
                    </Link>
                </div>

                {/* Nav */}
                <div style={{ padding: "12px 10px", flex: 1 }}>
                    <div style={{
                        fontSize: 10, fontWeight: 700, color: "#9ca3af",
                        letterSpacing: "0.1em", textTransform: "uppercase",
                        padding: "0 10px 8px",
                    }}>WORKSPACE</div>

                    {/* Main nav items */}
                    {NAV_ITEMS.map(item => {
                        const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                        return (
                            <Link key={item.href} href={item.href} style={{
                                display: "flex", alignItems: "center", justifyContent: "space-between",
                                padding: "9px 12px", borderRadius: 8, marginBottom: 2,
                                background: active ? "#f3f4f6" : "transparent",
                                textDecoration: "none", transition: "background 0.1s",
                            }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                    <span style={{ fontSize: 15 }}>{item.icon}</span>
                                    <span style={{
                                        fontSize: 14, fontWeight: active ? 600 : 400,
                                        color: active ? "#111" : "#6b7280",
                                    }}>{item.label}</span>
                                </div>
                            </Link>
                        );
                    })}

                    {/* Messages — before Quick Actions */}
                    {(() => {
                        const active = pathname.startsWith("/dashboard/messages");
                        return (
                            <Link href="/dashboard/messages" style={{
                                display: "flex", alignItems: "center", justifyContent: "space-between",
                                padding: "9px 12px", borderRadius: 8, marginBottom: 2,
                                background: active ? "#f3f4f6" : "transparent",
                                textDecoration: "none", transition: "background 0.1s",
                            }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                    <span style={{ fontSize: 15 }}>💬</span>
                                    <span style={{ fontSize: 14, fontWeight: active ? 600 : 400, color: active ? "#111" : "#6b7280" }}>Messages</span>
                                </div>
                                <span style={{
                                    fontSize: 11, fontWeight: 700, color: "#fff",
                                    background: "#111", borderRadius: 999,
                                    padding: "1px 7px", minWidth: 20, textAlign: "center",
                                }}>3</span>
                            </Link>
                        );
                    })()}

                    {/* Quick Actions — after Messages */}
                    <div style={{ marginTop: 8, marginBottom: 2 }}>
                        <div style={{
                            fontSize: 10, fontWeight: 700, color: "#9ca3af",
                            letterSpacing: "0.1em", textTransform: "uppercase",
                            padding: "8px 10px 6px",
                        }}>QUICK ACTIONS</div>
                        {QUICK_ACTIONS.map(a => (
                            <button key={a.label} style={{
                                width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                                padding: "9px 12px", borderRadius: 8, border: "none",
                                background: "transparent", color: "#6b7280", fontSize: 14,
                                cursor: "pointer", textAlign: "left", fontFamily: "inherit",
                                marginBottom: 2, transition: "background 0.1s",
                            }}
                                onMouseOver={e => (e.currentTarget.style.background = "#f9fafb")}
                                onMouseOut={e => (e.currentTarget.style.background = "transparent")}
                            >
                                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                    <span style={{ fontSize: 14, color: "#9ca3af" }}>{a.icon}</span>
                                    {a.label}
                                </div>
                                <span style={{ color: "#9ca3af", fontSize: 12 }}>›</span>
                            </button>
                        ))}
                    </div>
                </div>

                {/* User */}
                <div style={{ padding: "16px 20px", borderTop: "1px solid #f0f0f0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{
                            width: 32, height: 32, borderRadius: "50%", background: "#374151",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            color: "#fff", fontSize: 13, fontWeight: 700,
                        }}>A</div>
                        <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: "#111" }}>Agent</div>
                            <div style={{ fontSize: 11, color: "#9ca3af" }}>Admin</div>
                        </div>
                    </div>
                    <button onClick={() => router.push("/")} style={{
                        background: "none", border: "none", cursor: "pointer",
                        fontSize: 12, color: "#9ca3af", fontFamily: "inherit",
                    }}>↩</button>
                </div>
            </aside>

            {/* Main */}
            <main style={{ flex: 1, overflow: "auto" }}>
                {children}
            </main>
        </div>
    );
}
