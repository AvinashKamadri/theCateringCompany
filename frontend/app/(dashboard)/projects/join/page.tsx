"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { projectsApi } from "@/lib/api/projects";
import { toast } from "sonner";
import { KeyRound, Search, ArrowRight, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";

/** Extract the join code from either a raw code or a full invite URL */
function extractCode(input: string): string {
  const trimmed = input.trim();
  try {
    const url = new URL(trimmed);
    const param = url.searchParams.get("code");
    if (param) return param.trim();
  } catch {
    // Not a URL — use as-is
  }
  return trimmed;
}

export default function JoinProjectPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [input, setInput] = useState(searchParams.get("code") ?? "");
  const [preview, setPreview] = useState<{ id: string; title: string; status: string } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joined, setJoined] = useState(false);

  // Auto-preview when code arrives via URL
  useEffect(() => {
    const urlCode = searchParams.get("code");
    if (urlCode) {
      setPreviewing(true);
      projectsApi.lookupByCode(urlCode.trim()).then((result) => {
        if (result.found && result.project) setPreview(result.project);
        else toast.error("No project found for that link.");
      }).catch(() => toast.error("Could not look up project.")).finally(() => setPreviewing(false));
    }
  }, []);

  const handlePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    const code = extractCode(input);
    if (!code) return;
    setPreviewing(true);
    setPreview(null);
    try {
      const result = await projectsApi.lookupByCode(code);
      if (result.found && result.project) {
        setPreview(result.project);
      } else {
        toast.error("No project found. Double-check the code or link and try again.");
      }
    } catch (err: any) {
      toast.error(err.message || "Could not look up project");
    } finally {
      setPreviewing(false);
    }
  };

  const handleJoin = async () => {
    if (!preview) return;
    const code = extractCode(input);
    setJoining(true);
    try {
      const result = await projectsApi.joinByCode(code);
      if (result.already_member) {
        toast.success(`You are already a member of "${result.project.title}"`);
      } else {
        toast.success(`Joined "${result.project.title}" as ${result.role}`);
        setJoined(true);
      }
      setTimeout(() => router.push(`/projects/${result.project.id}`), 1200);
    } catch (err: any) {
      toast.error(err.message || "Failed to join project");
    } finally {
      setJoining(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 flex items-start justify-center pt-24 px-4">
      <div className="w-full max-w-md">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-neutral-500 hover:text-neutral-900 mb-6 text-sm transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        <div className="bg-white rounded-2xl border border-neutral-200 shadow-sm p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-neutral-100">
              <KeyRound className="h-5 w-5 text-neutral-700" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-neutral-900">Join a Project</h1>
              <p className="text-sm text-neutral-500">Enter a join code or paste an invite link</p>
            </div>
          </div>

          <form onSubmit={handlePreview} className="space-y-4">
            <div>
              <label htmlFor="code" className="block text-sm font-medium text-neutral-700 mb-2">
                Join code or invite URL
              </label>
              <input
                id="code"
                type="text"
                required
                value={input}
                onChange={(e) => { setInput(e.target.value); setPreview(null); setJoined(false); }}
                className="w-full px-4 py-3 rounded-lg border border-neutral-300 focus:ring-2 focus:ring-black focus:border-transparent outline-none transition font-mono text-sm"
                placeholder="e.g. johns-wedding-24985b6e or paste invite link"
                disabled={joining || joined}
              />
            </div>

            {!preview && (
              <button
                type="submit"
                disabled={!input.trim() || previewing || joining}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-neutral-100 text-neutral-700 font-medium hover:bg-neutral-200 transition disabled:opacity-50"
              >
                {previewing ? (
                  <><Loader2 className="h-4 w-4 animate-spin" />Looking up…</>
                ) : (
                  <><Search className="h-4 w-4" />Look up project</>
                )}
              </button>
            )}
          </form>

          {/* Preview card */}
          {preview && !joined && (
            <div className="mt-4 p-4 bg-neutral-50 border border-neutral-200 rounded-lg">
              <p className="text-xs text-neutral-500 font-medium uppercase tracking-wide mb-1">Found project</p>
              <p className="text-lg font-semibold text-neutral-900">{preview.title}</p>
              <p className="text-sm text-neutral-500 mt-0.5 capitalize">Status: {preview.status}</p>

              <button
                onClick={handleJoin}
                disabled={joining}
                className="mt-4 w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-black text-white font-semibold hover:bg-neutral-800 transition disabled:opacity-50"
              >
                {joining ? (
                  <><Loader2 className="h-4 w-4 animate-spin" />Joining…</>
                ) : (
                  <><ArrowRight className="h-4 w-4" />Join this project</>
                )}
              </button>
            </div>
          )}

          {joined && (
            <div className="mt-4 flex items-center gap-3 p-4 bg-neutral-50 border border-neutral-200 rounded-lg">
              <CheckCircle2 className="h-5 w-5 text-neutral-700 shrink-0" />
              <p className="text-sm text-neutral-700 font-medium">Joined! Redirecting to project…</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
