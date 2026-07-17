import { useEffect, useState } from "react";
import { getSecurityMode, setSecurityMode, login, loggedIn } from "./api";
import { Chat } from "./components/Chat";
import { Documents } from "./components/Documents";
import { RetrievalDebug } from "./components/RetrievalDebug";
import { Dashboard } from "./components/Dashboard";

type Tab = "chat" | "documents" | "debug" | "dashboard";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [mode, setMode] = useState<string>("…");
  const [canaries, setCanaries] = useState<number>(0);

  async function refresh() {
    const m = await getSecurityMode();
    setMode(m.mode);
    setCanaries((m.canaries ?? []).length);
  }
  useEffect(() => {
    refresh().catch(() => setMode("offline"));
  }, []);

  async function toggle() {
    if (!loggedIn()) {
      // demo admin seeded at startup
      await login("admin@ragguard.local", "ragguard-admin").catch(() => {});
    }
    const next = mode === "hardened" ? "naive" : "hardened";
    await setSecurityMode(next as "naive" | "hardened").catch((e) => alert(e.message));
    refresh();
  }

  const hardened = mode === "hardened";
  const tabs: Tab[] = ["chat", "documents", "debug", "dashboard"];

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold">InjectionRange</span>
          <span className="text-xs text-slate-400">RAG pipeline · VectorGuard target</span>
        </div>
        <button
          onClick={toggle}
          className={`px-3 py-1.5 rounded-md text-sm font-semibold border ${
            hardened
              ? "bg-emerald-600/20 border-emerald-500 text-emerald-300"
              : "bg-red-600/20 border-red-500 text-red-300"
          }`}
          title="Toggle security mode (auth-gated demo)"
        >
          mode: {mode} · {canaries} canaries · click to flip
        </button>
      </header>

      <nav className="flex gap-1 px-6 pt-3">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm rounded-t-md capitalize ${
              tab === t ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      <main className="p-6">
        {tab === "chat" && <Chat mode={mode} />}
        {tab === "documents" && <Documents />}
        {tab === "debug" && <RetrievalDebug mode={mode} />}
        {tab === "dashboard" && <Dashboard />}
      </main>
    </div>
  );
}
