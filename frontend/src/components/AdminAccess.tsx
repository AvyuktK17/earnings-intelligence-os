"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import {
  api,
  ApiError,
  clearAdminToken,
  getAdminToken,
  saveAdminToken,
  subscribeAdminToken,
} from "@/lib/api";

type CheckResult = "ok" | "invalid" | "unreachable";

export default function AdminAccess() {
  const [input, setInput] = useState("");
  const token = useSyncExternalStore(
    subscribeAdminToken,
    getAdminToken,
    () => null,
  );
  // The validation result is paired with the token it was computed for, so
  // a stale result is never shown after the token changes.
  const [checked, setChecked] = useState<{
    token: string;
    result: CheckResult;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function validate() {
      if (!token) return;
      try {
        await api.validateAdminToken();
        if (!cancelled) setChecked({ token, result: "ok" });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setChecked({ token, result: "invalid" });
        } else {
          setChecked({ token, result: "unreachable" });
        }
      }
    }

    validate();
    return () => {
      cancelled = true;
    };
  }, [token]);

  let label = "not connected";
  let tone = "text-faint";
  let dot = "bg-faint";
  if (token) {
    if (checked?.token !== token) {
      label = "checking…";
      tone = "text-muted";
      dot = "bg-faint";
    } else if (checked.result === "ok") {
      label = "connected";
      tone = "text-positive";
      dot = "bg-positive";
    } else if (checked.result === "invalid") {
      label = "invalid token";
      tone = "text-negative";
      dot = "bg-negative";
    } else {
      label = "unverified";
      tone = "text-muted";
      dot = "bg-faint";
    }
  }

  function handleSave() {
    const next = input.trim();
    if (!next) return;
    saveAdminToken(next);
    setInput("");
  }

  return (
    <div className="border-t border-edge px-3 py-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
          Admin Access
        </span>
        <span className="flex items-center gap-1 text-[10px] font-mono">
          <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
          <span className={tone}>{label}</span>
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
          disabled={!token}
          onClick={() => clearAdminToken()}
        >
          Clear
        </button>
      </div>
      <p className="mt-1.5 text-[10px] leading-snug text-faint">
        Stored in this browser session only and verified against the API.
        Required for review actions, promotion, extraction, and brief
        generation.
      </p>
    </div>
  );
}
