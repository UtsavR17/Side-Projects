/* FormEdge service worker — Web Push delivery (RFC 8030).
   Registered by components/PushToggle.tsx. Payload shape matches what
   backend/app/services/webpush_send.py sends: {title, body}. */

self.addEventListener("push", (event) => {
  let payload = { title: "FormEdge", body: "" };
  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch {
      payload.body = event.data.text();
    }
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "FormEdge", {
      body: payload.body || "",
      data: payload.data || {},
      tag: "formedge-alert", // coalesce repeated alerts into one notification
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) return client.focus();
      }
      return self.clients.openWindow("/");
    })
  );
});
