"use client";

import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LiveEvent {
  type?: string;
  races?: number;
  title?: string;
  category?: string;
}

/**
 * Streams backend SSE events ("new prediction available") instead of polling
 * the API (master plan §3 realtime row). Degrades silently if the API is down.
 */
export default function LiveUpdates() {
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let source: EventSource | null = null;
    let hideTimer: ReturnType<typeof setTimeout> | null = null;
    try {
      source = new EventSource(`${BASE}/api/events`);
      source.onmessage = (raw) => {
        try {
          const event: LiveEvent = JSON.parse(raw.data);
          let message: string | null = null;
          if (event.type === "predictions_updated") {
            message = `New predictions ready for ${event.races ?? "?"} race(s)`;
          } else if (event.type === "notification" && event.title) {
            message = event.title;
          }
          if (message) {
            setToast(message);
            if (hideTimer) clearTimeout(hideTimer);
            hideTimer = setTimeout(() => setToast(null), 6000);
          }
        } catch {
          /* heartbeat or malformed frame — ignore */
        }
      };
    } catch {
      /* EventSource unsupported — silent */
    }
    return () => {
      if (hideTimer) clearTimeout(hideTimer);
      if (source) source.close();
    };
  }, []);

  if (!toast) return null;
  return <div className="toast">{toast}</div>;
}
