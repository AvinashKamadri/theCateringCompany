import Link from "next/link";
import DotGrid from "@/components/ui/DotGrid";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-5/12 bg-black p-12 flex-col justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white">
            <span className="text-sm font-bold text-black">TC</span>
          </div>
          <span className="text-lg font-semibold text-white tracking-tight">TheCateringCompany</span>
        </Link>

        <div className="space-y-5">
          <h2 className="text-4xl font-bold text-white leading-tight">
            Manage events.<br />Build relationships.<br />Get paid.
          </h2>
          <p className="text-neutral-400 text-base leading-relaxed">
            The platform catering professionals use to manage projects, automate contracts, and collaborate with clients — all in one place.
          </p>
          <div className="pt-4 space-y-3">
            {[
              "Real-time project collaboration",
              "Version-controlled e-sign contracts",
              "Integrated payment processing",
            ].map((item) => (
              <div key={item} className="flex items-center gap-3">
                <div className="h-1.5 w-1.5 rounded-full bg-white shrink-0" />
                <span className="text-sm text-neutral-300">{item}</span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-neutral-600">© 2026 TheCateringCompany</p>
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
        <div className="relative z-10 w-full max-w-md">
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
