import Link from "next/link";
import { ArrowRight, CheckCircle2, Users, FileText, CreditCard, MessageSquare } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-white to-gray-50">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600">
              <span className="text-lg font-bold text-white">C</span>
            </div>
            <span className="text-xl font-bold text-gray-900">CateringCo</span>
          </div>
          <nav className="hidden md:flex items-center gap-6">
            <Link href="#features" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              How It Works
            </Link>
            <Link href="#pricing" className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
              Pricing
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/signin"
              className="text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="inline-flex h-9 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24 lg:pt-32 lg:pb-32">
        <div className="mx-auto max-w-4xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            Now in Beta
          </div>

          <h1 className="mb-6 text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl lg:text-7xl">
            Catering Management
            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent"> Simplified</span>
          </h1>

          <p className="mb-10 text-lg text-gray-600 sm:text-xl lg:text-2xl max-w-3xl mx-auto leading-relaxed">
            The all-in-one platform for catering professionals. Manage projects, collaborate with clients,
            handle contracts, and process payments — all in one place.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/signup"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 px-8 text-base font-semibold text-white hover:bg-blue-700 transition-colors shadow-lg shadow-blue-600/30 w-full sm:w-auto"
            >
              Start Free Trial
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="#features"
              className="inline-flex h-12 items-center justify-center rounded-lg border-2 border-gray-200 px-8 text-base font-semibold text-gray-700 hover:border-gray-300 hover:bg-gray-50 transition-colors w-full sm:w-auto"
            >
              Watch Demo
            </Link>
          </div>

          <p className="mt-6 text-sm text-gray-500">
            No credit card required • 14-day free trial • Cancel anytime
          </p>
        </div>

        {/* Hero Image / Dashboard Preview */}
        <div className="mt-16 mx-auto max-w-6xl">
          <div className="rounded-xl border border-gray-200 bg-white p-2 shadow-2xl">
            <div className="aspect-video rounded-lg bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center">
              <div className="text-center space-y-4">
                <div className="w-16 h-16 mx-auto rounded-full bg-blue-100 flex items-center justify-center">
                  <FileText className="w-8 h-8 text-blue-600" />
                </div>
                <p className="text-gray-500 text-sm">Dashboard Preview Coming Soon</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="border-t bg-white py-24">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              Everything you need to run your catering business
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Powerful features designed specifically for catering professionals
            </p>
          </div>

          <div className="mx-auto max-w-6xl grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {/* Feature 1 */}
            <div className="group rounded-xl border border-gray-200 bg-white p-8 hover:border-blue-300 hover:shadow-lg transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                <Users className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900">Project Collaboration</h3>
              <p className="text-gray-600">
                Slack-like channels for each project. Keep all client communication, files, and updates in one place.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group rounded-xl border border-gray-200 bg-white p-8 hover:border-blue-300 hover:shadow-lg transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900">Smart Contracts</h3>
              <p className="text-gray-600">
                Version-controlled contracts with e-signatures. Track changes and maintain a complete audit trail.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group rounded-xl border border-gray-200 bg-white p-8 hover:border-blue-300 hover:shadow-lg transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 text-green-600 group-hover:bg-green-600 group-hover:text-white transition-colors">
                <CreditCard className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900">Integrated Payments</h3>
              <p className="text-gray-600">
                Accept payments directly through Stripe. Automatic invoicing, deposits, and payment tracking.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="group rounded-xl border border-gray-200 bg-white p-8 hover:border-blue-300 hover:shadow-lg transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                <MessageSquare className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900">Real-time Updates</h3>
              <p className="text-gray-600">
                Live notifications and typing indicators. Stay connected with your team and clients instantly.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="group rounded-xl border border-gray-200 bg-white p-8 hover:border-blue-300 hover:shadow-lg transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-orange-100 text-orange-600 group-hover:bg-orange-600 group-hover:text-white transition-colors">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900">Task Management</h3>
              <p className="text-gray-600">
                Track deliverables, timelines, and milestones. Never miss a deadline with automated reminders.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="group rounded-xl border border-gray-200 bg-white p-8 hover:border-blue-300 hover:shadow-lg transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-pink-100 text-pink-600 group-hover:bg-pink-600 group-hover:text-white transition-colors">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-xl font-semibold text-gray-900">Document Storage</h3>
              <p className="text-gray-600">
                Secure cloud storage for menus, invoices, and photos. Share files with clients seamlessly.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t bg-gradient-to-br from-blue-600 to-indigo-700 py-20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="mb-6 text-4xl font-bold text-white sm:text-5xl">
              Ready to transform your catering business?
            </h2>
            <p className="mb-8 text-xl text-blue-100">
              Join hundreds of catering professionals who have simplified their workflow with CateringCo.
            </p>
            <Link
              href="/signup"
              className="inline-flex h-14 items-center justify-center gap-2 rounded-lg bg-white px-10 text-lg font-semibold text-blue-600 hover:bg-gray-50 transition-colors shadow-xl"
            >
              Start Your Free Trial
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-white py-12">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-blue-600 to-indigo-600">
                <span className="text-sm font-bold text-white">C</span>
              </div>
              <span className="font-semibold text-gray-900">CateringCo</span>
            </div>
            <p className="text-sm text-gray-500">
              © 2026 CateringCo. All rights reserved.
            </p>
            <div className="flex gap-6">
              <Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">
                Privacy
              </Link>
              <Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">
                Terms
              </Link>
              <Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">
                Contact
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
