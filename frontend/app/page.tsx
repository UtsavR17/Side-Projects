import Link from "next/link";
import { api, fmtDate, fmtTime, pct } from "@/lib/api";
import type {
  HistoryRow,
  LeaderboardModel,
  RaceDetail,
  RaceSummary,
} from "@/lib/types";

export const revalidate = 300; // ISR: pipeline refreshes data at most every few minutes

interface UpcomingResp {
  races: RaceSummary[];
}

/** Ensemble top pick (rank 1) of a race, from its stored predictions. */
function topPick(race: RaceDetail): { name: string; prob: number } | null {
  const runner = race.entries.find(
    (e) =>
      !e.scratched &&
      e.predictions?.some(
        (p) => p.model_name === "ensemble" && p.predicted_rank === 1
      )
  );
  const pred = runner?.predictions?.find(
    (p) => p.model_name === "ensemble" && p.predicted_rank === 1
  );
  return runner && pred ? { name: runner.horse_name, prob: pred.win_prob } : null;
}

function meetingDay(iso: string): string {
  return new Date(iso).toDateString();
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

  // Next meeting = races sharing the earliest upcoming date.
  const nextMeeting = races.length
    ? races.filter((r) => meetingDay(r.date) === meetingDay(races[0].date))
    : [];
  const meetingDetails = nextMeeting.length
    ? await Promise.all(
        nextMeeting.map((r) => api<RaceDetail>(`/api/races/${r.id}`))
      )
    : [];
  const meetingDate = nextMeeting[0]?.date;

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

      <h2>Next meeting</h2>
      {nextMeeting.length === 0 ? (
        <div className="empty">
          No upcoming meeting on file — import a nomination card via the{" "}
          <Link href="/admin">admin inbox</Link> or run the pipeline&rsquo;s import
          stage to add one.
        </div>
      ) : (
        <>
          <div className="card stat">
            <div className="value">
              {fmtDate(meetingDate)} · {fmtTime(nextMeeting[0].date)}
            </div>
            <div className="label">
              {nextMeeting[0].venue} — {nextMeeting.length} race
              {nextMeeting.length === 1 ? "" : "s"}
              {nextMeeting[0].meeting_no ? ` · Meeting ${nextMeeting[0].meeting_no}` : ""}
              {nextMeeting[0].race_time_label
                ? ` · first race ${nextMeeting[0].race_time_label}`
                : ""}
            </div>
          </div>
          <div className="card">
            <table>
              <thead>
                <tr>
                  <th className="num">R</th>
                  <th>Race</th>
                  <th className="num">Dist</th>
                  <th>Class</th>
                  <th>Top pick</th>
                  <th className="num">Win prob</th>
                </tr>
              </thead>
              <tbody>
                {nextMeeting.map((r, i) => {
                  const detail = meetingDetails[i];
                  const pick = detail ? topPick(detail) : null;
                  return (
                    <tr key={r.id}>
                      <td className="num">
                        <Link href={`/races/${r.id}`}>{r.race_no}</Link>
                      </td>
                      <td>
                        <Link href={`/races/${r.id}`}>
                          {r.race_name ?? `Race ${r.race_no}`}
                        </Link>
                      </td>
                      <td className="num">{r.distance_m ? `${r.distance_m}m` : "–"}</td>
                      <td>{r.race_class ?? "–"}</td>
                      <td>{pick ? pick.name : <span className="badge blue">pending</span>}</td>
                      <td className="num">{pick ? pct(pick.prob) : "–"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

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
