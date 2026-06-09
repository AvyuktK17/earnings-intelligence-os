"use client";

import { useState, useSyncExternalStore } from "react";
import {
  clearAdminToken,
  getAdminToken,
  saveAdminToken,
  subscribeAdminToken,
} from "@/lib/api";

export default function AdminAccess() {
  const [input, setInput] = useState("");
  const connected = useSyncExternalStore(
    subscribeAdminToken,
    () => getAdminToken() !== null,
    () => false,
  );

  function handleSave() {
    const token = input.trim();
    if (!token) return;
    saveAdminToken(token);
    setInput("");
  }

  return (
    <div className="border-t border-edge px-3 py-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
          Admin Access
        </span>
        <span className="flex items-center gap-1 text-[10px] font-mono">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              connected ? "bg-positive" : "bg-faint"
            }`}
          />
          <span className={connected ? "text-positive" : "text-faint"}>
            {connected ? "connected" : "not connected"}
          </span>
        </span>
      </div>
      <input
        type="password"
        autoComplete="off"
        className="mt-2 w-full rounded border border-edge bg-surface-raised px-2 py-1 font-mono text-[11px] text-foreground placeholder-faint focus:border-accent focus:outline-none"
        placeholder="Admin token"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSave();
        }}
      />
      <div className="mt-1.5 flex gap-1.5">
        <button
          className="flex-1 rounded border border-edge px-2 py-0.5 text-[11px] text-muted transition-colors hover:bg-surface-raised hover:text-foreground disabled:opacity-50"
          disabled={!input.trim()}
          onClick={handleSave}
        >
          Save
        </button>
        <button
          className="flex-1 rounded border border-edge px-2 py-0.5 text-[11px] text-muted transition-colors hover:bg-surface-raised hover:text-foreground disabled:opacity-50"
          disabled={!connected}
          onClick={() => clearAdminToken()}
        >
          Clear
        </button>
      </div>
      <p className="mt-1.5 text-[10px] leading-snug text-faint">
        Stored in this browser session only. Required for review actions,
        promotion, and brief generation.
      </p>
    </div>
  );
}
