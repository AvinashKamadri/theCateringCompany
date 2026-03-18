"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api/projects";
import { toast } from "sonner";
import { KeyRound, Search, ArrowRight, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";

export default function JoinProjectPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [preview, setPreview] = useState<{ id: string; title: string; status: string } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joined, setJoined] = useState(false);

  const handlePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setPreviewing(true);
    setPreview(null);
    try {
      const result = await projectsApi.lookupByCode(code.trim());
      if (result.found && result.project) {
        setPreview(result.project);
      } else {
        toast.error("No project found for that code. Double-check and try again.");
      }
    } catch (err: any) {
      toast.error(err.message || "Could not look up project");
    } finally {
      setPreviewing(false);
    }
  };

  const handleJoin = async () => {
    if (!preview) return;
    setJoining(true);
    try {
      const result = await projectsApi.joinByCode(code.trim());
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
    <div className="min-h-screen bg-gray-50 flex items-start justify-center pt-24 px-4">
      <div className="w-full max-w-md">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
              <KeyRound className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Join a Project</h1>
              <p className="text-sm text-gray-500">Enter the join code shared by the project owner</p>
            </div>
          </div>

          <form onSubmit={handlePreview} className="space-y-4">
            <div>
              <label htmlFor="code" className="block text-sm font-medium text-gray-700 mb-2">
                Project join code
              </label>
              <input
                id="code"
                type="text"
                required
                value={code}
                onChange={(e) => { setCode(e.target.value); setPreview(null); setJoined(false); }}
                className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition font-mono"
                placeholder="e.g. johns-wedding-24985b6e"
                disabled={joining || joined}
              />
            </div>

            {!preview && (
              <button
                type="submit"
                disabled={!code.trim() || previewing || joining}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-gray-100 text-gray-700 font-medium hover:bg-gray-200 transition disabled:opacity-50"
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
            <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-xs text-blue-600 font-medium uppercase tracking-wide mb-1">Found project</p>
              <p className="text-lg font-semibold text-gray-900">{preview.title}</p>
              <p className="text-sm text-gray-500 mt-0.5 capitalize">Status: {preview.status}</p>

              <button
                onClick={handleJoin}
                disabled={joining}
                className="mt-4 w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition disabled:opacity-50"
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
            <div className="mt-4 flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
              <p className="text-sm text-green-700 font-medium">Joined! Redirecting to project…</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
