"use client";

import { useCallback, useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN_KEY = "formedge_admin_token";

interface Flag {
  id: number;
  source: string;
  kind: string;
  message: string;
  url: string | null;
  context: Record<string, unknown> | null;
  resolved: boolean;
  created_at: string | null;
}

/**
 * Admin / data-quality view (master plan §11): review import & scrape flags and
 * push a saved page, CSV, pasted table or result PDF into the pipeline.
 */
export default function AdminPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [flags, setFlags] = useState<Flag[]>([]);
  const [showResolved, setShowResolved] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [content, setContent] = useState("");
  const [filename, setFilename] = useState("pasted.txt");
  const [defaultDate, setDefaultDate] = useState("");

  const authHeaders = useCallback(
    (): Record<string, string> => ({ Authorization: `Bearer ${token}` }),
    [token]
  );

  const loadFlags = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${BASE}/api/admin/flags?resolved=${showResolved}`, {
        headers: authHeaders(),
      });
      if (res.status === 401 || res.status === 403) {
        setError("Token rejected — sign in again.");
        return;
      }
      setFlags((await res.json()).flags ?? []);
    } catch (err) {
      setError(`Failed to load flags: ${err}`);
    }
  }, [authHeaders, showResolved]);

  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) setToken(saved);
  }, []);

  useEffect(() => {
    if (token) void loadFlags();
  }, [token, loadFlags]);

  async function login() {
    setError(null);
    setStatus(null);
    try {
      const res = await fetch(`${BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        setError(`Login failed (HTTP ${res.status}). Check the credentials.`);
        return;
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setStatus("Signed in.");
    } catch (err) {
      setError(`Cannot reach the API at ${BASE} — is it running? (${err})`);
    }
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setFlags([]);
    setStatus("Signed out.");
  }

  async function resolveFlag(id: number) {
    await fetch(`${BASE}/api/admin/flags/${id}/resolve`, {
      method: "POST",
      headers: authHeaders(),
    });
    void loadFlags();
  }

  async function onFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    setContent(await file.text().catch(() => ""));
    setStatus(`Loaded ${file.name} — press Import.`);
  }

  async function doImport() {
    if (!content.trim()) {
      setError("Nothing to import: choose a file or paste the page/CSV/table text.");
      return;
    }
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const body: Record<string, string> = { content, filename };
      if (defaultDate) body.default_date = defaultDate;
      const res = await fetch(`${BASE}/api/admin/import?kind=auto`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(`Import failed (HTTP ${res.status}): ${JSON.stringify(data.detail ?? data)}`);
        return;
      }
      setStatus(
        `Imported as ${data.kind}: races created ${data.races_created ?? 0} / updated ` +
          `${data.races_updated ?? 0}, entries +${data.entries ?? 0}, ` +
          `results ${data.results_written ?? 0}, warnings ${(data.warnings ?? []).length}`
      );
      void loadFlags();
    } catch (err) {
      setError(`Import error: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <>
        <h1>Admin sign-in</h1>
        <p className="subtitle">
          Needed for the data-quality view and the one-click importer.
        </p>
        <div className="card" style={{ maxWidth: 420 }}>
          <div>
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div style={{ marginTop: 12 }}>
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && login()}
            />
          </div>
          <button style={{ marginTop: 16 }} onClick={login}>
            Sign in
          </button>
          {error ? <p className="neg small">{error}</p> : null}
          <p className="muted small">
            Credentials default from <code>ADMIN_EMAIL</code> / <code>ADMIN_PASSWORD</code>{" "}
            in <code>backend/.env</code> (default <code>admin@example.com</code> /
            <code>admin1234</code>).
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <h1>Data quality &amp; import</h1>
      <p className="subtitle">
        Review what the scraper/importers could not parse, and push a saved page, CSV,
        pasted table or result PDF into the pipeline.
      </p>

      <div className="card">
        <h3>Import a document</h3>
        <div className="form-row">
          <div>
            <label>File (CSV / HTML / PDF)</label>
            <input type="file" onChange={onFile} accept=".csv,.html,.htm,.txt,.pdf" />
          </div>
          <div>
            <label>Fallback date (optional)</label>
            <input
              type="date"
              value={defaultDate}
              onChange={(e) => setDefaultDate(e.target.value)}
            />
          </div>
          <button onClick={doImport} disabled={busy}>
            {busy ? "Importing…" : "Import"}
          </button>
          <button onClick={signOut} style={{ background: "#39415a" }}>
            Sign out
          </button>
        </div>

        <label>…or paste the page / CSV / table content</label>
        <textarea
          rows={5}
          style={{
            width: "100%",
            background: "var(--panel-2)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 10,
            fontFamily: "ui-monospace, monospace",
          }}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Paste a race-card table (tab separated), a CSV, or the saved page HTML"
        />

        <p className="muted small mt">
          Tip: for a PDF, save it locally and use the CLI instead —
          <code> .\run-pipeline.ps1 import ".\file.pdf"</code> — the browser cannot read
          PDF bytes into this box.
        </p>
        {status ? <p className="pos small">{status}</p> : null}
        {error ? <p className="neg small">{error}</p> : null}
      </div>

      <h2>Data-quality flags</h2>
      <div className="form-row">
        <label>
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
          />{" "}
          show resolved
        </label>
        <button onClick={loadFlags} style={{ background: "#39415a" }}>
          Refresh
        </button>
      </div>

      {flags.length === 0 ? (
        <div className="empty">
          Nothing flagged — imports and scrapes parsed cleanly.
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Source</th>
                <th>Kind</th>
                <th>Message</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {flags.map((f) => (
                <tr key={f.id}>
                  <td className="small muted">
                    {f.created_at ? new Date(f.created_at).toLocaleString("en-GB") : "–"}
                  </td>
                  <td>{f.source}</td>
                  <td>
                    <span className="badge amber">{f.kind}</span>
                  </td>
                  <td className="small">
                    {f.message}
                    {f.context ? (
                      <span className="muted"> {JSON.stringify(f.context)}</span>
                    ) : null}
                  </td>
                  <td>
                    {f.resolved ? (
                      <span className="badge green">resolved</span>
                    ) : (
                      <button onClick={() => resolveFlag(f.id)}>Resolve</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}