"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Image from "next/image";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001";

export default function SignInPage() {
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ email, password }),
            });
            if (res.ok) {
                router.push("/dashboard");
            } else {
                const data = await res.json();
                setError(data?.message || "Invalid email or password.");
            }
        } catch {
            // Backend offline — demo mode
            router.push("/dashboard");
        } finally {
            setLoading(false);
        }
    }

    const inputStyle: React.CSSProperties = {
        width: "100%",
        padding: "10px 14px",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        fontSize: 14,
        color: "#111",
        background: "#fff",
        outline: "none",
        boxSizing: "border-box",
        transition: "border-color 0.15s",
        fontFamily: "inherit",
    };

    return (
        <div style={{ display: "flex", minHeight: "100vh", fontFamily: "'Inter', 'Segoe UI', sans-serif", background: "#fff" }}>
            {/* Left panel */}
            <div style={{
                width: "45%",
                background: "#f3f4f6",
                display: "flex",
                flexDirection: "column",
                padding: "48px 40px",
            }}>
                {/* Brand - text only, no icon */}
                <div style={{ marginBottom: 48 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: "#111", letterSpacing: "-0.01em" }}>The Catering Company</span>
                </div>

                {/* Food image */}
                <div style={{
                    borderRadius: 16, overflow: "hidden", marginBottom: 32,
                    boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
                    background: "#e5e7eb",
                    aspectRatio: "4/3",
                    position: "relative",
                    border: "6px solid #fff",
                }}>
                    <Image src="/food-signin.png" alt="Gourmet catering" fill style={{ objectFit: "cover" }} />
                </div>

                <h2 style={{ fontSize: 22, fontWeight: 700, color: "#111", marginBottom: 10, letterSpacing: "-0.02em" }}>
                    Welcome back
                </h2>
                <p style={{ fontSize: 14, color: "#6b7280", lineHeight: 1.7, textAlign: "center" }}>
                    Your catering assistant for menus, events, and collaborations. Manage your culinary projects with elegance and ease.
                </p>
                <div style={{ marginTop: 16, textAlign: "center" }}>
                    <a href="#" style={{ fontSize: 14, fontWeight: 600, color: "#111", textDecoration: "none" }}>
                        Learn more →
                    </a>
                </div>
            </div>

            {/* Right panel */}
            <div style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                padding: "48px 64px",
                background: "#fff",
            }}>
                <div style={{ maxWidth: 460, width: "100%" }}>
                    <h1 style={{ fontSize: 30, fontWeight: 700, color: "#111", marginBottom: 8, letterSpacing: "-0.02em" }}>
                        Sign in to your account
                    </h1>
                    <p style={{ fontSize: 15, color: "#6b7280", marginBottom: 32 }}>Please enter your details to continue</p>

                    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        <div>
                            <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 5 }}>Email Address</label>
                            <input style={inputStyle} type="email" placeholder="name@example.com" value={email} onChange={e => setEmail(e.target.value)} required
                                onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                        </div>

                        <div>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
                                <label style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}>Password</label>
                                <a href="#" style={{ fontSize: 12, color: "#6b7280", textDecoration: "none" }}
                                    onMouseOver={e => (e.currentTarget.style.color = "#111")}
                                    onMouseOut={e => (e.currentTarget.style.color = "#6b7280")}>
                                    Forgot password?
                                </a>
                            </div>
                            <input style={inputStyle} type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required
                                onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                        </div>

                        {error && (
                            <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#dc2626" }}>
                                {error}
                            </div>
                        )}

                        <button type="submit" disabled={loading} style={{
                            width: "100%", padding: "12px", borderRadius: 8, background: "#111",
                            color: "#fff", fontWeight: 600, fontSize: 15, border: "none", cursor: loading ? "wait" : "pointer",
                            marginTop: 2, transition: "background 0.15s", fontFamily: "inherit",
                            opacity: loading ? 0.7 : 1,
                        }}>
                            {loading ? "Signing in…" : "Sign In"}
                        </button>
                    </form>

                    {/* Divider */}
                    <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0" }}>
                        <div style={{ flex: 1, height: 1, background: "#e5e7eb" }} />
                        <span style={{ fontSize: 11, color: "#9ca3af", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>or continue with</span>
                        <div style={{ flex: 1, height: 1, background: "#e5e7eb" }} />
                    </div>

                    {/* Social buttons - Google only */}
                    <button style={{
                        width: "100%", padding: "11px", borderRadius: 8, background: "#fff", border: "1px solid #e5e7eb",
                        fontSize: 14, fontWeight: 500, color: "#374151", cursor: "pointer",
                        display: "flex", alignItems: "center", justifyContent: "center", gap: 10, fontFamily: "inherit",
                    }}
                        onMouseOver={e => (e.currentTarget.style.background = "#f9fafb")}
                        onMouseOut={e => (e.currentTarget.style.background = "#fff")}>
                        <svg width="16" height="16" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                        Sign in with Google
                    </button>

                    <p style={{ textAlign: "center", fontSize: 13, color: "#6b7280", marginTop: 24 }}>
                        Don&apos;t have an account?{" "}
                        <Link href="/signup" style={{ color: "#111", fontWeight: 600, textDecoration: "none" }}>Sign up</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
