"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/auth-store";

function SignInForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, isAuthenticated } = useAuthStore();

  // If already authenticated (e.g. back-button after login), push forward
  useEffect(() => {
    if (isAuthenticated) {
      router.replace(searchParams?.get('redirect') || '/projects');
    }
  }, [isAuthenticated, router, searchParams]);
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
    <div className="tc-glossy rounded-2xl p-8">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-black mb-1">Welcome back</h1>
        <p className="text-sm text-neutral-500">Sign in to continue planning your event.</p>
      </div>

      {error && (
        <div className="mb-5 px-4 py-3 rounded-lg bg-neutral-100 border border-neutral-200">
          <p className="text-sm text-black">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
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
              placeholder="Enter your password"
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
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="tc-btn-glossy w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-semibold"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Signing in…
            </>
          ) : (
            "Sign in"
          )}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-neutral-500">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-medium text-black hover:underline">
          Sign up
        </Link>
      </p>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="tc-glossy rounded-2xl p-8" />}>
      <SignInForm />
    </Suspense>
  );
}
