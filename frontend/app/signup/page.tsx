"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Image from "next/image";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001";

export default function SignUpPage() {
    const router = useRouter();
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");
    const [company, setCompany] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [agreed, setAgreed] = useState(false);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError("");
        if (!agreed) { setError("Please agree to the Terms of Service and Privacy Policy."); return; }
        if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/api/auth/signup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ email, password, firstName, lastName }),
            });
            if (res.ok) {
                router.push("/dashboard");
            } else {
                const data = await res.json();
                setError(data?.message || "Signup failed. Please try again.");
            }
        } catch {
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
                position: "relative",
            }}>
                {/* Brand name only - no logo icon */}
                <div style={{ marginBottom: 32 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: "#111", letterSpacing: "-0.01em" }}>The Catering Company</span>
                </div>

                {/* Food image */}
                <div style={{
                    borderRadius: 16, overflow: "hidden", marginBottom: 32,
                    boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
                    background: "#e5e7eb",
                    aspectRatio: "4/3",
                    position: "relative",
                }}>
                    <Image src="/food-signup.png" alt="Catering food" fill style={{ objectFit: "cover" }} />
                </div>

                <div style={{
                    marginTop: "auto",
                    padding: "20px",
                    borderRadius: 12,
                    background: "rgba(0,0,0,0.04)",
                    borderLeft: "3px solid #e5e7eb",
                }}>
                    <p style={{ fontSize: 13, color: "#6b7280", lineHeight: 1.7, fontStyle: "italic", margin: 0 }}>
                        &ldquo;Great catering is not just about food — it&apos;s about crafting unforgettable moments, one event at a time.&rdquo;
                    </p>
                    <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 8 }}>— The TCC Philosophy</p>
                </div>
            </div>

            {/* Right panel */}
            <div style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                padding: "48px 48px",
                background: "#fff",
            }}>
                <div style={{ maxWidth: 480, width: "100%" }}>
                    <h1 style={{ fontSize: 30, fontWeight: 700, color: "#111", marginBottom: 28, letterSpacing: "-0.02em" }}>
                        Create your account
                    </h1>

                    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                        {/* Name row */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                            <div>
                                <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 5 }}>First Name</label>
                                <input style={inputStyle} placeholder="Jane" value={firstName} onChange={e => setFirstName(e.target.value)} required
                                    onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                            </div>
                            <div>
                                <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 5 }}>Last Name</label>
                                <input style={inputStyle} placeholder="Doe" value={lastName} onChange={e => setLastName(e.target.value)} required
                                    onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                            </div>
                        </div>

                        <div>
                            <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 5 }}>Company (optional)</label>
                            <input style={inputStyle} placeholder="Gourmet Events Co." value={company} onChange={e => setCompany(e.target.value)}
                                onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                        </div>

                        <div>
                            <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 5 }}>Email address</label>
                            <input style={inputStyle} type="email" placeholder="jane@example.com" value={email} onChange={e => setEmail(e.target.value)} required
                                onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                        </div>

                        <div>
                            <label style={{ fontSize: 13, fontWeight: 500, color: "#374151", display: "block", marginBottom: 5 }}>Password</label>
                            <input style={inputStyle} type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required
                                onFocus={e => (e.target.style.borderColor = "#111")} onBlur={e => (e.target.style.borderColor = "#e5e7eb")} />
                        </div>

                        {/* Terms */}
                        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
                            <input type="checkbox" id="terms" checked={agreed} onChange={e => setAgreed(e.target.checked)}
                                style={{ width: 16, height: 16, cursor: "pointer", accentColor: "#111" }} />
                            <label htmlFor="terms" style={{ fontSize: 13, color: "#6b7280", cursor: "pointer" }}>
                                I agree to the{" "}
                                <a href="#" style={{ color: "#111", fontWeight: 600, textDecoration: "underline" }}>Terms of Service</a>
                                {" "}and{" "}
                                <a href="#" style={{ color: "#111", fontWeight: 600, textDecoration: "underline" }}>Privacy Policy</a>
                            </label>
                        </div>

                        {error && (
                            <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#dc2626" }}>
                                {error}
                            </div>
                        )}

                        <button type="submit" disabled={loading} style={{
                            width: "100%", padding: "12px", borderRadius: 8, background: "#111",
                            color: "#fff", fontWeight: 600, fontSize: 15, border: "none", cursor: loading ? "wait" : "pointer",
                            marginTop: 4, transition: "background 0.15s", fontFamily: "inherit",
                            opacity: loading ? 0.7 : 1,
                        }}>
                            {loading ? "Creating account…" : "Create Account"}
                        </button>
                    </form>

                    {/* Divider */}
                    <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0" }}>
                        <div style={{ flex: 1, height: 1, background: "#e5e7eb" }} />
                        <span style={{ fontSize: 12, color: "#9ca3af", fontWeight: 500 }}>Or continue with</span>
                        <div style={{ flex: 1, height: 1, background: "#e5e7eb" }} />
                    </div>

                    {/* Google button */}
                    <button style={{
                        width: "100%", padding: "11px", borderRadius: 8, background: "#fff",
                        border: "1px solid #e5e7eb", fontSize: 14, fontWeight: 500, color: "#374151",
                        cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                        gap: 10, fontFamily: "inherit", transition: "background 0.15s",
                    }}
                        onMouseOver={e => (e.currentTarget.style.background = "#f9fafb")}
                        onMouseOut={e => (e.currentTarget.style.background = "#fff")}>
                        <svg width="18" height="18" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                        </svg>
                        Sign up with Google
                    </button>

                    <p style={{ textAlign: "center", fontSize: 13, color: "#6b7280", marginTop: 24 }}>
                        Already have an account?{" "}
                        <Link href="/signin" style={{ color: "#111", fontWeight: 600, textDecoration: "none" }}>Sign in</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
