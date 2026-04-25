"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2, ArrowRight } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/auth-store";

// Background images that rotate every 3 seconds.
// Replace these with your final 3 catering images when ready.
const HERO_IMAGES = [
  "/cat-bg2.jpg",
  "/catering-bg1.jpg",
  "/catering-bg3.jpg",
];

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, isAuthenticated } = useAuthStore();

  // If already authenticated (e.g. back-button after login), push forward
  useEffect(() => {
    if (isAuthenticated) {
      router.replace(searchParams?.get("redirect") || "/projects");
    }
  }, [isAuthenticated, router, searchParams]);

  // Cycle background image every 3 seconds
  const [imageIndex, setImageIndex] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setImageIndex((i) => (i + 1) % HERO_IMAGES.length);
    }, 3000);
    return () => clearInterval(id);
  }, []);

  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [formData, setFormData] = useState({ email: "", password: "" });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const data: any = await apiClient.post("/auth/login", formData);
      if (data.accessToken) {
        document.cookie = `app_jwt=${data.accessToken}; path=/; max-age=7200; SameSite=Lax`;
      }
      setUser(data.user);
      const redirect = searchParams?.get("redirect");
      router.replace(redirect || "/projects");
    } catch (err: any) {
      setError(err.message || "Invalid email or password.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="min-h-screen relative overflow-hidden bg-neutral-900">
      {/* Background slideshow */}
      <div className="absolute inset-0">
        {HERO_IMAGES.map((src, i) => (
          <img
            key={src}
            src={src}
            alt=""
            className="absolute inset-0 w-full h-full object-cover transition-opacity duration-[1200ms] ease-in-out"
            style={{
              opacity: i === imageIndex ? 1 : 0,
              filter: "saturate(1.08) contrast(1.06)",
            }}
          />
        ))}
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(180deg, rgba(14,14,14,0.45) 0%, rgba(14,14,14,0.25) 30%, rgba(14,14,14,0.55) 70%, rgba(14,14,14,0.85) 100%)",
          }}
        />
      </div>

      {/* Top brand strip */}
      <div className="relative z-10 flex justify-between items-center px-8 lg:px-14 py-7">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full flex items-center justify-center backdrop-blur-md bg-white/15 border border-white/25">
            <span className="text-[11px] font-bold text-white">TC</span>
          </div>
          <div className="text-white">
            <div className="text-sm font-semibold tracking-tight drop-shadow">TheCateringCompany</div>
          </div>
        </Link>
      </div>

      {/* Center content */}
      <div
        className="relative z-10 flex flex-col items-center justify-center px-6 pb-16"
        style={{ minHeight: "calc(100vh - 200px)" }}
      >
        {/* Hero tagline */}
        <div className="text-center mb-8 lg:mb-10 max-w-3xl">
          <div className="inline-flex items-center gap-3">
            <div className="w-12 h-[1px] bg-white/70" />
            <span className="text-[11px] tracking-[0.3em] uppercase text-white/85 font-medium drop-shadow">
              Welcome back
            </span>
            <div className="w-12 h-[1px] bg-white/70" />
          </div>
          <h1
            className="font-[family-name:var(--font-cormorant)] text-white font-medium leading-[1.05] mt-6 drop-shadow-[0_2px_18px_rgba(0,0,0,0.6)]"
            style={{ fontSize: "clamp(40px, 5vw, 78px)" }}
          >
            Crafted gatherings,<br />
            <span className="italic font-normal">to the last detail.</span>
          </h1>
        </div>

        {/* Form card */}
        <div className="w-full max-w-lg">
          <div
            className="rounded-2xl p-10 lg:p-12"
            style={{
              background: "#fcfaf5",
              boxShadow: "0 40px 90px -30px rgba(0,0,0,0.55)",
            }}
          >
            <div className="text-center mb-8">
              <h2 className="font-[family-name:var(--font-cormorant)] text-3xl font-medium tracking-tight text-neutral-900">
                Sign in <span className="italic font-normal text-neutral-600">to continue</span>
              </h2>
            </div>

            {error && (
              <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label
                  htmlFor="email"
                  className="block text-[10px] font-semibold uppercase tracking-[0.3em] mb-1 text-neutral-500"
                >
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  disabled={isLoading}
                  placeholder="you@example.com"
                  className="w-full bg-white border border-neutral-200 rounded-xl py-3 px-4 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                />
              </div>

              <div>
                <div className="flex justify-between items-end mb-1">
                  <label
                    htmlFor="password"
                    className="block text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-500"
                  >
                    Password
                  </label>
                  <button type="button" className="text-[11px] hover:underline font-medium text-neutral-900">
                    Forgot?
                  </button>
                </div>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    disabled={isLoading}
                    placeholder="••••••••"
                    className="w-full bg-white border border-neutral-200 rounded-xl py-3 pl-4 pr-12 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={isLoading}
                    className="absolute right-0 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-900 transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-4 rounded-full text-[12px] font-semibold tracking-[0.25em] uppercase flex items-center justify-center gap-3 mt-2 bg-neutral-900 text-white hover:-translate-y-px hover:shadow-[0_18px_32px_-16px_rgba(14,14,14,0.5)] transition-all disabled:opacity-60"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <>
                    Sign in <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-7 pt-6 border-t border-neutral-200 text-center">
              <p className="text-sm text-neutral-600">
                Don&apos;t have an account?{" "}
                <Link href="/signup" className="font-semibold hover:underline ml-1 text-neutral-900">
                  Create one →
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom tagline */}
      <div className="absolute bottom-6 left-0 right-0 z-10 px-8 lg:px-14">
        <div className="flex justify-center items-end text-white/80">
          <div className="font-[family-name:var(--font-cormorant)] italic text-base lg:text-lg drop-shadow">
            You celebrate. We&apos;ll handle the rest.
          </div>
        </div>
      </div>
    </section>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-neutral-900" />}>
      <SignInForm />
    </Suspense>
  );
}
