"use client";

import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "formedge_admin_token"; // same token the admin page stores

type State = "hidden" | "off" | "on";

/** base64url -> Uint8Array for PushManager.subscribe's applicationServerKey. */
function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/**
 * Header bell: opt into Web Push (RFC 8291) for new predictions & alerts.
 * Renders nothing when the browser lacks push support or nobody is signed
 * in (the admin page stores the JWT under the same key).
 */
export default function PushToggle() {
  const [state, setState] = useState<State>("hidden");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
    if (!localStorage.getItem(TOKEN_KEY)) return;
    setState("off");
    (async () => {
      try {
        const reg = await navigator.serviceWorker.register("/sw.js");
        const sub = await reg.pushManager.getSubscription();
        if (sub) setState("on");
      } catch {
        /* registration failed (e.g. unsupported context) — stay hidden */
      }
    })();
  }, []);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    setNote(null);
    try {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        setState("hidden");
        return;
      }
      const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

      if (state === "on") {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          await fetch(`${BASE}/api/push/unsubscribe`, {
            method: "POST",
            headers,
            body: JSON.stringify({ endpoint: sub.endpoint }),
          });
          await sub.unsubscribe();
        }
        setState("off");
        return;
      }

      const keyRes = await fetch(`${BASE}/api/push/vapid-public-key`);
      if (!keyRes.ok) {
        setNote(
          keyRes.status === 503
            ? "Web push is not enabled on the API (see README: gen_vapid.py)."
            : "Could not fetch the VAPID key from the API."
        );
        return;
      }
      const { key } = (await keyRes.json()) as { key: string };
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key),
      });
      const info = sub.toJSON();
      const res = await fetch(`${BASE}/api/push/subscribe`, {
        method: "POST",
        headers,
        body: JSON.stringify({ endpoint: info.endpoint, keys: info.keys }),
      });
      if (!res.ok) {
        await sub.unsubscribe();
        setNote(res.status === 401 || res.status === 403 ? "Sign in again to enable alerts." : "API rejected the subscription.");
        return;
      }
      setState("on");
    } catch {
      setNote("Push subscription failed (browser or network issue).");
    } finally {
      setBusy(false);
    }
  }

  if (state === "hidden") return null;
  const on = state === "on";
  return (
    <button
      className={`nav-btn${on ? " on" : ""}`}
      onClick={() => void toggle()}
      disabled={busy}
      aria-pressed={on}
      title={note || (on ? "Browser alerts on — click to disable" : "Enable browser alerts for new predictions")}
    >
      {on ? "🔔 Alerts on" : "🔕 Alerts"}
    </button>
  );
}
