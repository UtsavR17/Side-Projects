import Link from "next/link";
import { api, fmtDate, pct } from "@/lib/api";
import type { HistoryRow } from "@/lib/types";

export const revalidate = 300;

export default async function AccuracyPage() {
  const data = await api<{ history: HistoryRow[] }>("/api/predictions/history?limit=60");
  const rows = data?.history ?? [];
  const hits = rows.filter((r) => r.hit).length;
  const rate = rows.length ? hits / rows.length : null;

  return (
    <>
      <h1>Prediction history &amp; accuracy</h1>
      <p className="subtitle">
        Ensemble top pick vs actual result for recent completed races (§9).
      </p>

      <div className="grid cols-3">
        <div className="card stat">
          <div className="value">{rows.length}</div>
          <div className="label">Scored races</div>
        </div>
        <div className="card stat">
          <div className="value">{hits}</div>
          <div className="label">Top-pick hits</div>
        </div>
        <div className="card stat">
          <div className="value">{pct(rate, 1)}</div>
          <div className="label">Hit rate</div>
        </div>
      </div>

      <div className="card mt">
        {rows.length === 0 ? (
          <div className="empty">
            No scored predictions yet — run the predict + evaluate pipeline stages.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">R</th>
                <th>Going</th>
                <th className="num">Dist</th>
                <th className="num">Top pick</th>
                <th className="num">Win prob</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <tr key={h.race.id}>
                  <td>
                    <Link href={`/races/${h.race.id}`}>{fmtDate(h.race.date)}</Link>
                  </td>
                  <td className="num">{h.race.race_no}</td>
                  <td>{h.race.track_condition ?? "–"}</td>
                  <td className="num">
                    {h.race.distance_m ? `${h.race.distance_m}m` : "–"}
                  </td>
                  <td>
                    <Link href={`/horses/${h.top_pick_horse_id}`}>
                      Horse #{h.top_pick_horse_id}
                    </Link>
                  </td>
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
        )}
      </div>
    </>
  );
}
