"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2, KeyRound } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/auth-store";

export default function SignUpPage() {
  const router = useRouter();
  const setUser = useAuthStore((state) => state.setUser);
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
    return { bars: 3, label: "Strong", color: "bg-black" };
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
      setUser(data.user);
      if (data.joined_project?.id) {
        router.push(`/projects/${data.joined_project.id}`);
      } else {
        router.push("/chat");
      }
    } catch (err: any) {
      setError(err.message || "Failed to create account.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-8 shadow-sm">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-black mb-1">Create your account</h1>
        <p className="text-sm text-neutral-500">Get started with TheCateringCompany.</p>
      </div>

      {error && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-neutral-100 border border-neutral-200">
          <p className="text-sm text-black">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="first_name" className="block text-sm font-medium text-black mb-1.5">
              First name
            </label>
            <input
              id="first_name"
              type="text"
              required
              value={formData.first_name}
              onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition"
              placeholder="John"
              disabled={isLoading}
            />
          </div>
          <div>
            <label htmlFor="last_name" className="block text-sm font-medium text-black mb-1.5">
              Last name
            </label>
            <input
              id="last_name"
              type="text"
              required
              value={formData.last_name}
              onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition"
              placeholder="Doe"
              disabled={isLoading}
            />
          </div>
        </div>

        {/* Email */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-black mb-1.5">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition"
            placeholder="you@example.com"
            disabled={isLoading}
          />
        </div>

        {/* Password */}
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-black mb-1.5">
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              required
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition pr-11"
              placeholder="Create a strong password"
              disabled={isLoading}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-black transition-colors"
              disabled={isLoading}
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
              <p className="text-xs text-neutral-500">{strength.label}</p>
            </div>
          )}
        </div>

        {/* Phone (optional) */}
        <div>
          <label htmlFor="primary_phone" className="block text-sm font-medium text-black mb-1.5">
            Phone <span className="text-neutral-400 font-normal">(optional)</span>
          </label>
          <input
            id="primary_phone"
            type="tel"
            value={formData.primary_phone}
            onChange={(e) => setFormData({ ...formData, primary_phone: e.target.value })}
            className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition"
            placeholder="+1 (555) 000-0000"
            disabled={isLoading}
          />
        </div>

        {/* Project code (optional) */}
        <div className="rounded-lg border border-dashed border-neutral-300 p-4">
          <button
            type="button"
            onClick={() => setShowProjectCode(!showProjectCode)}
            className="flex items-center gap-2 text-sm font-medium text-neutral-600 hover:text-black transition-colors w-full"
            disabled={isLoading}
          >
            <KeyRound className="h-4 w-4 shrink-0" />
            {showProjectCode ? "Hide project code" : "Join an existing project?"}
            <span className="text-neutral-400 font-normal">(optional)</span>
          </button>
          {showProjectCode && (
            <div className="mt-3">
              <label htmlFor="project_code" className="block text-xs text-neutral-500 mb-1.5">
                Project join code
              </label>
              <input
                id="project_code"
                type="text"
                value={formData.project_code}
                onChange={(e) =>
                  setFormData({ ...formData, project_code: e.target.value.trim() })
                }
                className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-300 bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent transition text-sm font-mono"
                placeholder="e.g. johns-wedding-24985b6e"
                disabled={isLoading}
              />
              <p className="mt-1.5 text-xs text-neutral-400">
                Ask the project owner for the join code — you&apos;ll be added as a collaborator.
              </p>
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-black text-white text-sm font-semibold hover:bg-neutral-800 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating account…
            </>
          ) : (
            "Create account"
          )}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-neutral-500">
        Already have an account?{" "}
        <Link href="/signin" className="font-medium text-black hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
