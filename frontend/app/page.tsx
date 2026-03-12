"use client";

import Link from "next/link";
import Image from "next/image";

export default function LandingPage() {
  return (
    <div style={{ fontFamily: "'Inter', 'Segoe UI', sans-serif", background: "#fff", minHeight: "100vh" }}>

      {/* ===== NAV ===== */}
      <header style={{
        position: "sticky", top: 0, zIndex: 50,
        borderBottom: "1px solid #f0f0f0",
        background: "rgba(255,255,255,0.95)",
        backdropFilter: "blur(8px)",
      }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", padding: "0 32px", height: 60, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, background: "#111", borderRadius: 8,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: "#fff",
            }}>🍴</div>
            <span style={{ fontSize: 15, fontWeight: 700, color: "#111" }}>The Catering Company</span>
          </div>

          <nav style={{ display: "flex", alignItems: "center", gap: 28 }}>
            {["Features", "Menus", "Pricing", "About"].map(n => (
              <a key={n} href="#" style={{ fontSize: 14, color: "#6b7280", textDecoration: "none", fontWeight: 450 }}
                onMouseOver={e => (e.currentTarget.style.color = "#111")}
                onMouseOut={e => (e.currentTarget.style.color = "#6b7280")}>{n}</a>
            ))}
          </nav>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Link href="/signin" style={{
              fontSize: 14, fontWeight: 500, color: "#374151",
              textDecoration: "none", padding: "8px 16px", borderRadius: 8,
              border: "1px solid #e5e7eb", transition: "all 0.15s",
            }}
              onMouseOver={e => { e.currentTarget.style.background = "#f9fafb"; }}
              onMouseOut={e => { e.currentTarget.style.background = "transparent"; }}
            >Sign In</Link>
            <Link href="/signup" style={{
              fontSize: 14, fontWeight: 600, color: "#fff",
              textDecoration: "none", padding: "8px 18px", borderRadius: 8,
              background: "#111", transition: "all 0.15s",
            }}
              onMouseOver={e => (e.currentTarget.style.background = "#374151")}
              onMouseOut={e => (e.currentTarget.style.background = "#111")}
            >Get Started</Link>
          </div>
        </div>
      </header>

      {/* ===== HERO ===== */}
      <section style={{ maxWidth: 1160, margin: "0 auto", padding: "80px 32px 60px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 60, alignItems: "center" }}>
        <div>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "#f3f4f6", borderRadius: 999, padding: "5px 14px", marginBottom: 24,
            fontSize: 12, fontWeight: 600, color: "#374151",
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e" }} />
            Now accepting 2026 bookings
          </div>

          <h1 style={{ fontSize: 48, fontWeight: 800, color: "#111", letterSpacing: "-0.03em", lineHeight: 1.1, marginBottom: 20 }}>
            Catering excellence,<br />
            <span style={{ color: "#6b7280", fontWeight: 600 }}>effortlessly managed.</span>
          </h1>

          <p style={{ fontSize: 16, color: "#6b7280", lineHeight: 1.7, marginBottom: 32, maxWidth: 440 }}>
            The all-in-one platform for catering professionals. Plan events, design menus, collaborate with clients, and handle payments — all in one elegant workspace.
          </p>

          <div style={{ display: "flex", gap: 12 }}>
            <Link href="/signup" style={{
              padding: "13px 28px", borderRadius: 10, background: "#111",
              color: "#fff", fontWeight: 600, fontSize: 15, textDecoration: "none",
              transition: "background 0.15s",
            }}>Start free trial →</Link>
            <Link href="/signin" style={{
              padding: "13px 24px", borderRadius: 10, background: "#fff",
              color: "#374151", fontWeight: 500, fontSize: 15, textDecoration: "none",
              border: "1px solid #e5e7eb",
            }}>Sign in</Link>
          </div>

          <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 14 }}>
            No credit card required · 14-day free trial
          </p>
        </div>

        {/* Hero image */}
        <div style={{ borderRadius: 20, overflow: "hidden", boxShadow: "0 20px 60px rgba(0,0,0,0.12)", aspectRatio: "4/3", position: "relative", background: "#f3f4f6" }}>
          <Image src="/food-signup.png" alt="Catering setup" fill style={{ objectFit: "cover" }} />
        </div>
      </section>

      {/* ===== STATS ===== */}
      <section style={{ borderTop: "1px solid #f0f0f0", borderBottom: "1px solid #f0f0f0", padding: "32px 0" }}>
        <div style={{ maxWidth: 1160, margin: "0 auto", padding: "0 32px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 24, textAlign: "center" }}>
          {[
            { n: "2,400+", l: "Events managed" },
            { n: "98%", l: "Client satisfaction" },
            { n: "£12M+", l: "Payments processed" },
            { n: "340+", l: "Catering companies" },
          ].map(s => (
            <div key={s.l}>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#111", letterSpacing: "-0.02em" }}>{s.n}</div>
              <div style={{ fontSize: 13, color: "#9ca3af", marginTop: 4 }}>{s.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ===== FEATURES ===== */}
      <section style={{ maxWidth: 1160, margin: "0 auto", padding: "80px 32px" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <h2 style={{ fontSize: 34, fontWeight: 800, color: "#111", letterSpacing: "-0.02em", marginBottom: 12 }}>
            Everything your catering team needs
          </h2>
          <p style={{ fontSize: 15, color: "#6b7280", maxWidth: 500, margin: "0 auto" }}>
            Streamline every step from initial enquiry to event completion.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 24 }}>
          {[
            { icon: "🎉", title: "Event Management", desc: "Track every event — dates, venues, guest counts, and delivery status all in one view." },
            { icon: "🍽️", title: "Menu Builder", desc: "Create and share custom menus with dietary filters. Get instant client approvals." },
            { icon: "💳", title: "Payments", desc: "Send invoices, track deposits and balances. Automated reminders and payment status." },
            { icon: "💬", title: "AI Catering Assistant", desc: "Real-time client chat powered by AI. Browse menus, assign staff, start bookings." },
          ].map(f => (
            <div key={f.title} style={{
              padding: 28, borderRadius: 16, border: "1px solid #f0f0f0", background: "#fff",
              transition: "all 0.2s",
            }}
              onMouseOver={e => { e.currentTarget.style.borderColor = "#e5e7eb"; e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.06)"; }}
              onMouseOut={e => { e.currentTarget.style.borderColor = "#f0f0f0"; e.currentTarget.style.boxShadow = "none"; }}
            >
              <div style={{ fontSize: 28, marginBottom: 14 }}>{f.icon}</div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: "#111", marginBottom: 8 }}>{f.title}</h3>
              <p style={{ fontSize: 14, color: "#6b7280", lineHeight: 1.6 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section style={{ background: "#111", padding: "64px 32px", textAlign: "center" }}>
        <h2 style={{ fontSize: 32, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: 14 }}>
          Ready to elevate your catering business?
        </h2>
        <p style={{ fontSize: 15, color: "#9ca3af", marginBottom: 28 }}>
          Join hundreds of catering professionals already managing their business with TCC.
        </p>
        <Link href="/signup" style={{
          display: "inline-flex", padding: "14px 32px", borderRadius: 10,
          background: "#fff", color: "#111", fontWeight: 700, fontSize: 15,
          textDecoration: "none",
        }}>Create your free account →</Link>
      </section>

      {/* ===== FOOTER ===== */}
      <footer style={{ borderTop: "1px solid #f0f0f0", padding: "28px 32px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 24, height: 24, background: "#111", borderRadius: 5, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "#fff" }}>🍴</div>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>The Catering Company</span>
        </div>
        <p style={{ fontSize: 12, color: "#9ca3af" }}>© 2026 The Catering Company. All rights reserved.</p>
      </footer>
    </div>
  );
}
