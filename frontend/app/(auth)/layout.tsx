"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import DotGrid from "@/components/ui/DotGrid";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen">
      {/* Left panel — catering hero photo with tagline overlay */}
      <div className="hidden lg:flex lg:w-5/12 relative overflow-hidden bg-black">
        {/* Background photo. Swap the src to any image in /public if desired. */}
        <img
          src="/login-bg1.jpg"
          alt="A curated catering spread"
          className="absolute inset-0 h-full w-full object-cover"
        />
        {/* Dark gradient for readability top + bottom */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.10) 35%, rgba(0,0,0,0.35) 70%, rgba(0,0,0,0.85) 100%)",
          }}
        />

        <div className="relative z-10 flex flex-col justify-between w-full p-12">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 w-fit">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/95 backdrop-blur">
              <span className="text-sm font-bold text-black">TC</span>
            </div>
            <span className="text-lg font-semibold text-white tracking-tight drop-shadow">
              TheCateringCompany
            </span>
          </Link>

          {/* Tagline */}
          <div className="space-y-3">
            <h2 className="text-3xl xl:text-4xl font-semibold text-white leading-tight tracking-tight drop-shadow-[0_2px_12px_rgba(0,0,0,0.5)]">
              Your event,<br />crafted to the last detail.
            </h2>
            <p className="text-sm text-neutral-300 leading-relaxed max-w-md">
              TheCateringCompany — AI-assisted planning, curated menus, and contracts ready to sign.
            </p>
          </div>
        </div>
      </div>

      {/* Right panel — DotGrid bg + form */}
      <div className="flex-1 relative flex items-center justify-center p-8 bg-neutral-50 overflow-hidden">
        {/* Interactive dot grid fills the entire right panel */}
        <div className="absolute inset-0">
          <DotGrid
            dotSize={6}
            gap={22}
            baseColor="#d4d4d4"
            activeColor="#000000"
            proximity={100}
            shockRadius={220}
            shockStrength={4}
            resistance={800}
            returnDuration={1.5}
          />
        </div>

        {/* Form sits above the grid */}
        <div key={pathname} className="relative z-10 w-full max-w-md tc-page-enter">
          {/* Mobile logo */}
          <div className="lg:hidden mb-8">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-black">
                <span className="text-sm font-bold text-white">TC</span>
              </div>
              <span className="text-lg font-semibold text-black tracking-tight">TheCateringCompany</span>
            </Link>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
