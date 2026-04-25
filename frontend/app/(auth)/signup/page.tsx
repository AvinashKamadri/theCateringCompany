"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2, KeyRound, ArrowRight } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/auth-store";

// Background images that rotate every 3 seconds.
const HERO_IMAGES = [
  "/catering-food1.jpg.jpg",
  "/catering-food2.png",
  "/catering-food3.png",
];

export default function SignUpPage() {
  const router = useRouter();
  const { setUser, isAuthenticated } = useAuthStore();

  // If already authenticated (e.g. back-button after signup), push forward
  useEffect(() => {
    if (isAuthenticated) router.replace("/projects");
  }, [isAuthenticated, router]);

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
  const [showProjectCode, setShowProjectCode] = useState(false);
  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    primary_phone: "",
    project_code: "",
  });

  const getPasswordStrength = (pw: string) => {
    if (!pw) return { bars: 0, label: "", color: "" };
    if (pw.length < 6) return { bars: 1, label: "Weak", color: "bg-neutral-400" };
    if (pw.length < 10 || !/[A-Z]/.test(pw) || !/[0-9]/.test(pw))
      return { bars: 2, label: "Fair", color: "bg-neutral-600" };
    return { bars: 3, label: "Strong", color: "bg-neutral-900" };
  };
  const strength = getPasswordStrength(formData.password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const payload: any = { ...formData };
      if (!payload.project_code) delete payload.project_code;
      if (!payload.primary_phone) delete payload.primary_phone;
      const data: any = await apiClient.post("/auth/signup", payload);
      if (data.accessToken) {
        document.cookie = `app_jwt=${data.accessToken}; path=/; max-age=7200; SameSite=Lax`;
      }
      setUser(data.user);
      if (data.joined_project?.id) {
        router.replace(`/projects/${data.joined_project.id}`);
      } else {
        router.replace("/chat");
      }
    } catch (err: any) {
      setError(err.message || "Failed to create account.");
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
              "linear-gradient(180deg, rgba(14,14,14,0.35) 0%, rgba(14,14,14,0.15) 30%, rgba(14,14,14,0.35) 70%, rgba(14,14,14,0.65) 100%)",
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
      <div className="relative z-10 flex flex-col items-center justify-center px-6 pt-4 pb-20">
        {/* Hero tagline */}
        <div className="text-center mb-8 max-w-3xl">
          <div className="inline-flex items-center gap-3">
            <div className="w-12 h-[1px] bg-white/70" />
            <span className="text-[11px] tracking-[0.3em] uppercase text-white/85 font-medium drop-shadow">
              Begin your story
            </span>
            <div className="w-12 h-[1px] bg-white/70" />
          </div>
          <h1
            className="font-[family-name:var(--font-cormorant)] text-white font-medium leading-[1.05] mt-6 drop-shadow-[0_2px_18px_rgba(0,0,0,0.6)]"
            style={{ fontSize: "clamp(36px, 4.5vw, 70px)" }}
          >
            Plan something<br />
            <span className="italic font-normal">unforgettable.</span>
          </h1>
        </div>

        {/* Form card */}
        <div className="w-full max-w-xl">
          <div
            className="rounded-2xl p-9 lg:p-11"
            style={{
              background: "#fcfaf5",
              boxShadow: "0 40px 90px -30px rgba(0,0,0,0.55)",
            }}
          >
            <div className="text-center mb-7">
              <div className="text-[11px] tracking-[0.3em] uppercase mb-1 text-neutral-500">
                Let&apos;s begin
              </div>
              <h2 className="font-[family-name:var(--font-cormorant)] text-3xl font-medium tracking-tight text-neutral-900">
                Create <span className="italic font-normal text-neutral-600">your account</span>
              </h2>
            </div>

            {error && (
              <div className="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Name */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="first_name"
                    className="block text-[10px] font-semibold uppercase tracking-[0.3em] mb-1 text-neutral-500"
                  >
                    First
                  </label>
                  <input
                    id="first_name"
                    type="text"
                    required
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    disabled={isLoading}
                    placeholder="John"
                    className="w-full bg-transparent border-0 border-b border-neutral-200 py-3 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                  />
                </div>
                <div>
                  <label
                    htmlFor="last_name"
                    className="block text-[10px] font-semibold uppercase tracking-[0.3em] mb-1 text-neutral-500"
                  >
                    Last
                  </label>
                  <input
                    id="last_name"
                    type="text"
                    required
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    disabled={isLoading}
                    placeholder="Doe"
                    className="w-full bg-transparent border-0 border-b border-neutral-200 py-3 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                  />
                </div>
              </div>

              {/* Email */}
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
                  className="w-full bg-transparent border-0 border-b border-neutral-200 py-3 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                />
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="password"
                  className="block text-[10px] font-semibold uppercase tracking-[0.3em] mb-1 text-neutral-500"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    disabled={isLoading}
                    placeholder="Create a strong password"
                    className="w-full bg-transparent border-0 border-b border-neutral-200 py-3 pr-10 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
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
                {formData.password && (
                  <div className="mt-2 space-y-1">
                    <div className="flex gap-1">
                      {[1, 2, 3].map((lvl) => (
                        <div
                          key={lvl}
                          className={`h-1 flex-1 rounded-full transition-colors ${
                            lvl <= strength.bars ? strength.color : "bg-neutral-200"
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-[11px] text-neutral-500 tracking-wide">{strength.label}</p>
                  </div>
                )}
              </div>

              {/* Phone (optional) */}
              <div>
                <label
                  htmlFor="primary_phone"
                  className="block text-[10px] font-semibold uppercase tracking-[0.3em] mb-1 text-neutral-500"
                >
                  Phone <span className="normal-case tracking-normal opacity-60">(optional)</span>
                </label>
                <input
                  id="primary_phone"
                  type="tel"
                  value={formData.primary_phone}
                  onChange={(e) => setFormData({ ...formData, primary_phone: e.target.value })}
                  disabled={isLoading}
                  placeholder="+1 (555) 000-0000"
                  className="w-full bg-transparent border-0 border-b border-neutral-200 py-3 text-[15px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                />
              </div>

              {/* Project code (optional) */}
              <div className="rounded-lg border border-dashed border-neutral-300 p-3">
                <button
                  type="button"
                  onClick={() => setShowProjectCode(!showProjectCode)}
                  disabled={isLoading}
                  className="flex items-center gap-2 text-sm font-medium text-neutral-600 hover:text-neutral-900 transition-colors w-full"
                >
                  <KeyRound className="h-4 w-4 shrink-0" />
                  {showProjectCode ? "Hide project code" : "Join an existing project?"}
                  <span className="text-neutral-400 font-normal text-xs">(optional)</span>
                </button>
                {showProjectCode && (
                  <div className="mt-3">
                    <input
                      id="project_code"
                      type="text"
                      value={formData.project_code}
                      onChange={(e) =>
                        setFormData({ ...formData, project_code: e.target.value.trim() })
                      }
                      disabled={isLoading}
                      placeholder="e.g. johns-wedding-24985b6e"
                      className="w-full bg-transparent border-0 border-b border-neutral-200 py-2.5 text-[14px] font-mono text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-900 transition-colors"
                    />
                    <p className="mt-2 text-[11px] text-neutral-500">
                      Ask the project owner for the join code — you&apos;ll be added as a collaborator.
                    </p>
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-4 rounded-full text-[12px] font-semibold tracking-[0.25em] uppercase flex items-center justify-center gap-3 mt-2 bg-neutral-900 text-white hover:-translate-y-px hover:shadow-[0_18px_32px_-16px_rgba(14,14,14,0.5)] transition-all disabled:opacity-60"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating account…
                  </>
                ) : (
                  <>
                    Create account <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-neutral-200 text-center">
              <p className="text-sm text-neutral-600">
                Already have an account?{" "}
                <Link href="/signin" className="font-semibold hover:underline ml-1 text-neutral-900">
                  Sign in →
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom tagline */}
      <div className="absolute bottom-6 left-0 right-0 z-10 px-8 lg:px-14">
        <div className="flex justify-between items-end text-white/80">
          <div className="font-[family-name:var(--font-cormorant)] italic text-base lg:text-lg drop-shadow">
            Every occasion, made memorable.
          </div>
          <div className="text-[10px] tracking-[0.25em] uppercase">© 2026 · TheCateringCompany</div>
        </div>
      </div>
    </section>
  );
}
