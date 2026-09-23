import Link from "next/link";
import { api, fmtDate, fmtTime } from "@/lib/api";
import type { RaceSummary } from "@/lib/types";

export const revalidate = 300;

export default async function RacesPage() {
  const data = await api<{ races: RaceSummary[] }>("/api/races?limit=100");
  const races = data?.races ?? [];

  return (
    <>
      <h1>Upcoming races</h1>
      <p className="subtitle">Fixtures as ingested by the background scraper.</p>
      {races.length === 0 ? (
        <div className="empty">No upcoming races yet.</div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">R</th>
                <th>Name</th>
                <th className="num">Dist</th>
                <th>Class</th>
                <th>Going</th>
                <th>Weather</th>
              </tr>
            </thead>
            <tbody>
              {races.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/races/${r.id}`}>
                      {fmtDate(r.date)} · {fmtTime(r.date)}
                    </Link>
                  </td>
                  <td className="num">{r.race_no}</td>
                  <td>{r.race_name ?? <span className="muted">–</span>}</td>
                  <td className="num">{r.distance_m ? `${r.distance_m}m` : "–"}</td>
                  <td>{r.race_class ?? "–"}</td>
                  <td>{r.track_condition ?? "–"}</td>
                  <td>{r.weather ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
