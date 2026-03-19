import Link from "next/link";
import { ArrowRight, Users, FileText, CreditCard, MessageSquare } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      {/* Header */}
      <header className="border-b border-neutral-200 bg-white sticky top-0 z-50">
        <div className="container mx-auto flex h-16 items-center justify-between px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-black">
              <span className="text-sm font-bold text-white">TC</span>
            </div>
            <span className="text-lg font-semibold tracking-tight text-black">TheCateringCompany</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/signin"
              className="text-sm font-medium text-neutral-600 hover:text-black transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="inline-flex h-9 items-center justify-center rounded-lg bg-black px-4 text-sm font-medium text-white hover:bg-neutral-800 transition-colors"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-6 lg:px-8 pt-24 pb-28">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="mb-5 text-5xl font-bold tracking-tight text-black sm:text-6xl">
            Catering management,<br />done right.
          </h1>
          <p className="mb-10 text-lg text-neutral-500 max-w-xl mx-auto leading-relaxed">
            One platform for projects, client collaboration, contracts, and payments.
            Built for catering professionals.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/signup"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-black px-7 text-sm font-semibold text-white hover:bg-neutral-800 transition-colors w-full sm:w-auto"
            >
              Create account
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/signin"
              className="inline-flex h-11 items-center justify-center rounded-lg border border-neutral-200 px-7 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors w-full sm:w-auto"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-neutral-200 bg-neutral-50 py-20">
        <div className="container mx-auto px-6 lg:px-8">
          <div className="mx-auto max-w-xl text-center mb-14">
            <h2 className="text-3xl font-bold tracking-tight text-black">
              Everything in one place
            </h2>
            <p className="mt-3 text-neutral-500">
              Purpose-built tools for catering businesses.
            </p>
          </div>

          <div className="mx-auto max-w-5xl grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: Users,
                title: "Project Collaboration",
                desc: "Per-project channels for clients, staff, and partners.",
              },
              {
                icon: FileText,
                title: "Smart Contracts",
                desc: "Version-controlled contracts with e-signature workflows.",
              },
              {
                icon: CreditCard,
                title: "Payments",
                desc: "Stripe-powered invoicing, deposits, and tracking.",
              },
              {
                icon: MessageSquare,
                title: "Real-time Messaging",
                desc: "Live chat with typing indicators and notifications.",
              },
            ].map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="rounded-xl border border-neutral-200 bg-white p-6 hover:border-black transition-colors"
              >
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-neutral-100">
                  <Icon className="h-5 w-5 text-black" />
                </div>
                <h3 className="mb-1.5 text-sm font-semibold text-black">{title}</h3>
                <p className="text-sm text-neutral-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-neutral-200 bg-black py-20">
        <div className="container mx-auto px-6 lg:px-8 text-center">
          <h2 className="mb-4 text-3xl font-bold text-white sm:text-4xl">
            Ready to get started?
          </h2>
          <p className="mb-8 text-neutral-400">
            Join catering professionals who manage their business with TheCateringCompany.
          </p>
          <Link
            href="/signup"
            className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-white px-8 text-base font-semibold text-black hover:bg-neutral-100 transition-colors"
          >
            Create your account
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-neutral-200 bg-white py-8">
        <div className="container mx-auto px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-black">
                <span className="text-xs font-bold text-white">TC</span>
              </div>
              <span className="text-sm font-semibold text-black">TheCateringCompany</span>
            </div>
            <p className="text-xs text-neutral-400">© 2026 TheCateringCompany. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
