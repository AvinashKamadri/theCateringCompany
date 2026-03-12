"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";

type Msg = {
    id: string;
    role: "assistant" | "user";
    text: string;
    time: string;
    cards?: { img: string; title: string; desc: string }[];
};

const initMessages: Msg[] = [
    {
        id: "1",
        role: "assistant",
        text: "Hello! I'm your TCC Assistant. I can help you browse our seasonal /menus, connect you with our /chef, or start a new /booking.\n\nWhat are you planning today?",
        time: "09:41 AM",
    },
    {
        id: "2",
        role: "user",
        text: "I'm looking for /menu options for a /wedding in September.",
        time: "09:42 AM",
    },
    {
        id: "3",
        role: "assistant",
        text: "Excellent! September is a beautiful time for outdoor ceremonies. Our /manager Sarah specialises in wedding logistics.\n\nHere are our most popular wedding packages for autumn:",
        time: "09:42 AM",
        cards: [
            { img: "/banquet.png", title: "The Grand Banquet", desc: "Full 5-course service" },
            { img: "/cocktail.png", title: "Boutique Cocktail", desc: "Elegant hors d'oeuvres" },
        ],
    },
];


const COMMANDS = [
    { icon: "📅", cmd: "/event", desc: "Wedding, Corporate, Funeral…" },
    { icon: "✕", cmd: "/menu", desc: "Browse catalog" },
    { icon: "👥", cmd: "/staff", desc: "/chef, /manager, /eventplanner" },
];

const MENU_OPTIONS = ["Casuals", "Signature Dishes", "Chefs Specials"];

function renderText(text: string) {
    const parts = text.split(/(\/\w+)/g);
    return parts.map((p, i) =>
        p.startsWith("/") ? (
            <code key={i} style={{
                background: "#f3f4f6", border: "1px solid #e5e7eb",
                borderRadius: 4, padding: "1px 6px", fontSize: 13, color: "#374151", fontFamily: "monospace",
            }}>{p}</code>
        ) : (
            <span key={i}>{p}</span>
        )
    );
}

export default function MessagesPage() {
    const [messages, setMessages] = useState<Msg[]>(initMessages);
    const [input, setInput] = useState("");
    const [showCommands, setShowCommands] = useState(false);
    const [showMenuOptions, setShowMenuOptions] = useState(false);
    const [typing, setTyping] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    function handleInput(v: string) {
        setInput(v);
        if (v === "/") { setShowCommands(true); setShowMenuOptions(false); }
        else if (v.includes("/menu")) { setShowMenuOptions(true); setShowCommands(false); }
        else { setShowCommands(false); setShowMenuOptions(false); }
    }

    function insertCommand(cmd: string) {
        setInput(cmd + " ");
        setShowCommands(false);
        setShowMenuOptions(false);
    }

    function sendMessage(e: React.FormEvent) {
        e.preventDefault();
        if (!input.trim()) return;
        const now = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
        const userMsg: Msg = { id: Date.now().toString(), role: "user", text: input.trim(), time: now };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setShowCommands(false);
        setShowMenuOptions(false);

        setTyping(true);
        setTimeout(() => {
            setTyping(false);
            const replies = [
                "Absolutely! I can arrange that for your event. Our team will be in touch within 24 hours to confirm the booking details.",
                "Great choice! Our /chef recommends pairing this with seasonal ingredients. Shall I send you the full menu PDF?",
                "Of course! I've noted your requirements. Would you like to schedule a call with our /manager to discuss further?",
                "Perfect timing! We have availability in September. Let me check the calendar and get back to you with available dates.",
            ];
            const replyMsg: Msg = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                text: replies[Math.floor(Math.random() * replies.length)],
                time: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
            };
            setMessages(prev => [...prev, replyMsg]);
        }, 1800);
    }

    return (
        <div style={{
            display: "flex", height: "100vh", overflow: "hidden",
            fontFamily: "'Inter', 'Segoe UI', sans-serif", background: "#f3f4f6",
            alignItems: "center", justifyContent: "center",
        }}>
            {/* Main widget */}
            <div style={{
                display: "flex", width: "100%", height: "100%",
                background: "#fff",
                boxShadow: "0 8px 40px rgba(0,0,0,0.10)",
                overflow: "hidden",
            }}>


                {/* ===== MAIN CHAT ===== */}
                <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
                    {/* Header */}
                    <div style={{
                        padding: "16px 24px", borderBottom: "1px solid #f0f0f0",
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                    }}>
                        <div>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ width: 30, height: 30, borderRadius: "50%", background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>🤖</div>
                                <div>
                                    <div style={{ fontSize: 15, fontWeight: 700, color: "#111" }}>Catering Assistant</div>
                                    <div style={{ fontSize: 12, color: "#9ca3af" }}>Ask about menus, events, or collaborations</div>
                                </div>
                            </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            {/* Avatars */}
                            <div style={{ display: "flex" }}>
                                {["SJ", "RP", "TC"].map((a, i) => (
                                    <div key={a} style={{
                                        width: 26, height: 26, borderRadius: "50%", border: "2px solid #fff",
                                        marginLeft: i === 0 ? 0 : -8,
                                        background: ["#7c3aed", "#0891b2", "#059669"][i],
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        fontSize: 9, fontWeight: 700, color: "#fff",
                                    }}>{a}</div>
                                ))}
                                <div style={{
                                    width: 26, height: 26, borderRadius: "50%", border: "2px solid #fff",
                                    marginLeft: -8, background: "#374151",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    fontSize: 9, fontWeight: 700, color: "#fff",
                                }}>+4</div>
                            </div>
                            <button style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "#9ca3af", padding: "0 4px" }}>✕</button>
                        </div>
                    </div>


                    {/* Messages */}
                    <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
                        {messages.map(msg => (
                            <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: msg.role === "user" ? "flex-end" : "flex-start", gap: 4 }}>
                                {msg.role === "assistant" ? (
                                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, maxWidth: "75%" }}>
                                        <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, flexShrink: 0 }}>🤖</div>
                                        <div>
                                            <div style={{
                                                background: "#f3f4f6", borderRadius: "0 12px 12px 12px",
                                                padding: "12px 14px", fontSize: 14, color: "#374151", lineHeight: 1.6,
                                            }}>
                                                {renderText(msg.text)}
                                            </div>
                                            {msg.cards && (
                                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
                                                    {msg.cards.map(c => (
                                                        <div key={c.title} style={{ borderRadius: 10, overflow: "hidden", border: "1px solid #e5e7eb", background: "#fff" }}>
                                                            <div style={{ height: 100, position: "relative" }}>
                                                                <Image src={c.img} alt={c.title} fill style={{ objectFit: "cover" }} />
                                                            </div>
                                                            <div style={{ padding: "8px 10px" }}>
                                                                <div style={{ fontSize: 13, fontWeight: 600, color: "#111" }}>{c.title}</div>
                                                                <div style={{ fontSize: 11, color: "#9ca3af" }}>{c.desc}</div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                            <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>ASSISTANT • {msg.time}</div>
                                        </div>
                                    </div>
                                ) : (
                                    <div style={{ display: "flex", alignItems: "flex-end", gap: 10, maxWidth: "75%", flexDirection: "row-reverse" }}>
                                        <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#374151", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "#fff", flexShrink: 0 }}>👤</div>
                                        <div>
                                            <div style={{
                                                background: "#111", borderRadius: "12px 0 12px 12px",
                                                padding: "12px 14px", fontSize: 14, color: "#fff", lineHeight: 1.6,
                                            }}>
                                                {renderText(msg.text)}
                                            </div>
                                            <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4, textAlign: "right" }}>YOU • {msg.time}</div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}

                        {typing && (
                            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                                <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>🤖</div>
                                <div style={{ background: "#f3f4f6", borderRadius: "0 12px 12px 12px", padding: "12px 18px", display: "flex", gap: 4, alignItems: "center" }}>
                                    {[0, 1, 2].map(i => (
                                        <div key={i} style={{
                                            width: 7, height: 7, borderRadius: "50%", background: "#9ca3af",
                                            animation: "bounce 1s ease infinite",
                                            animationDelay: `${i * 0.15}s`,
                                        }} />
                                    ))}
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Command popups */}
                    {(showCommands || showMenuOptions) && (
                        <div style={{
                            position: "absolute", bottom: 72, left: 24,
                            background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12,
                            boxShadow: "0 8px 24px rgba(0,0,0,0.1)", overflow: "hidden",
                            display: "flex", zIndex: 10,
                        }}>
                            {showCommands && (
                                <div style={{ padding: 8, minWidth: 200 }}>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: "#9ca3af", letterSpacing: "0.1em", padding: "4px 10px 8px", textTransform: "uppercase" }}>COMMANDS</div>
                                    {COMMANDS.map(c => (
                                        <button key={c.cmd} onClick={() => insertCommand(c.cmd)}
                                            style={{
                                                width: "100%", display: "flex", alignItems: "center", gap: 10,
                                                padding: "9px 10px", border: "none", background: "transparent",
                                                cursor: "pointer", borderRadius: 8, textAlign: "left", fontFamily: "inherit",
                                            }}
                                            onMouseOver={e => (e.currentTarget.style.background = "#f9fafb")}
                                            onMouseOut={e => (e.currentTarget.style.background = "transparent")}
                                        >
                                            <div style={{ width: 28, height: 28, background: "#f3f4f6", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13 }}>{c.icon}</div>
                                            <div>
                                                <div style={{ fontSize: 13, fontWeight: 600, color: "#111" }}>{c.cmd}</div>
                                                <div style={{ fontSize: 11, color: "#9ca3af" }}>{c.desc}</div>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                            {showMenuOptions && (
                                <div style={{ padding: 8, minWidth: 160, borderLeft: showCommands ? "1px solid #f0f0f0" : "none" }}>
                                    <div style={{ fontSize: 10, fontWeight: 700, color: "#9ca3af", letterSpacing: "0.1em", padding: "4px 10px 8px", textTransform: "uppercase" }}>MENU OPTIONS</div>
                                    {MENU_OPTIONS.map(o => (
                                        <button key={o} onClick={() => insertCommand(o)}
                                            style={{
                                                width: "100%", display: "flex", alignItems: "center", gap: 10,
                                                padding: "9px 10px", border: "none", background: "transparent",
                                                cursor: "pointer", borderRadius: 8, textAlign: "left", fontFamily: "inherit", fontSize: 13, color: "#374151",
                                            }}
                                            onMouseOver={e => (e.currentTarget.style.background = "#f9fafb")}
                                            onMouseOut={e => (e.currentTarget.style.background = "transparent")}
                                        >
                                            <span style={{ fontSize: 15 }}>🥘</span>
                                            {o}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Input */}
                    <form onSubmit={sendMessage} style={{
                        padding: "12px 24px 16px",
                        borderTop: "1px solid #f0f0f0",
                        display: "flex", alignItems: "center", gap: 10, background: "#fff",
                    }}>
                        <input
                            value={input}
                            onChange={e => handleInput(e.target.value)}
                            placeholder="Ask about events, menus…"
                            style={{
                                flex: 1, padding: "10px 16px", border: "1px solid #e5e7eb", borderRadius: 24,
                                fontSize: 14, color: "#374151", background: "#f9fafb", outline: "none",
                                fontFamily: "inherit", transition: "border-color 0.15s",
                            }}
                            onFocus={e => (e.target.style.borderColor = "#111")}
                            onBlur={e => (e.target.style.borderColor = "#e5e7eb")}
                        />
                        <button type="submit" style={{
                            width: 36, height: 36, borderRadius: "50%", background: "#111",
                            border: "none", cursor: "pointer", display: "flex", alignItems: "center",
                            justifyContent: "center", color: "#fff", fontSize: 14, flexShrink: 0,
                        }}>›</button>
                    </form>
                    <div style={{ textAlign: "center", fontSize: 11, color: "#9ca3af", paddingBottom: 10 }}>
                        Try typing <code style={{ background: "#f3f4f6", padding: "1px 5px", borderRadius: 4 }}>/</code> for staff{" "}
                        &nbsp; Try typing <code style={{ background: "#f3f4f6", padding: "1px 5px", borderRadius: 4 }}>@</code> for collaborations
                    </div>
                </div>
            </div>

            <style>{`
        @keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }
      `}</style>
        </div>
    );
}
