import Link from "next/link";
import { api, fmtDate, fmtTime, pct } from "@/lib/api";
import type { HistoryRow, LeaderboardModel, RaceSummary } from "@/lib/types";

export const revalidate = 300; // ISR: pipeline refreshes data at most every few minutes

interface UpcomingResp {
  races: RaceSummary[];
}

export default async function DashboardPage() {
  const [upcoming, history, leaderboard] = await Promise.all([
    api<UpcomingResp>("/api/races"),
    api<{ history: HistoryRow[] }>("/api/predictions/history?limit=5"),
    api<{ models: LeaderboardModel[] }>("/api/leaderboard"),
  ]);

  const races = upcoming?.races ?? [];
  const hist = history?.history ?? [];
  const hits = hist.filter((h) => h.hit).length;
  const models = leaderboard?.models ?? [];
  const ensemble = models.find((m) => m.model_name === "ensemble")?.latest;

  return (
    <>
      <h1>Dashboard</h1>
      <p className="subtitle">
        Mauritius racing intelligence — pre-computed predictions, explanations and model
        tracking.
      </p>

      <div className="grid cols-3">
        <div className="card stat">
          <div className="value">{races.length}</div>
          <div className="label">Upcoming races</div>
        </div>
        <div className="card stat">
          <div className="value">
            {hist.length ? `${hits}/${hist.length}` : "–"}
          </div>
          <div className="label">Recent top-pick hits</div>
        </div>
        <div className="card stat">
          <div className="value">{pct(ensemble?.accuracy ?? null, 0)}</div>
          <div className="label">Ensemble top-1 (latest)</div>
        </div>
      </div>

      <h2>Upcoming races</h2>
      {races.length === 0 ? (
        <div className="empty">
          No upcoming races cached yet — the background pipeline will fill this in after
          the next scrape. Run <code>python seed_demo.py</code> for demo data.
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">R</th>
                <th>Venue</th>
                <th className="num">Dist</th>
                <th>Going</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {races.slice(0, 10).map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/races/${r.id}`}>
                      {fmtDate(r.date)} {fmtTime(r.date)}
                    </Link>
                  </td>
                  <td className="num">{r.race_no}</td>
                  <td>{r.venue}</td>
                  <td className="num">{r.distance_m ? `${r.distance_m}m` : "–"}</td>
                  <td>{r.track_condition ?? "–"}</td>
                  <td>
                    <span className="badge blue">{r.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Latest prediction history</h2>
      {hist.length === 0 ? (
        <div className="empty">
          No scored predictions yet — run the train/predict/evaluate stages.
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Race</th>
                <th>Top pick</th>
                <th className="num">Win prob</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {hist.map((h) => (
                <tr key={h.race.id}>
                  <td>
                    <Link href={`/races/${h.race.id}`}>
                      R{h.race.race_no} · {fmtDate(h.race.date)}
                    </Link>
                  </td>
                  <td>Horse #{h.top_pick_horse_id}</td>
                  <td className="num">{pct(h.top_pick_prob)}</td>
                  <td>
                    {h.hit ? (
                      <span className="badge green">HIT</span>
                    ) : (
                      <span className="badge red">miss</span>
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
