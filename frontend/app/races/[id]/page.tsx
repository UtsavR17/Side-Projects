import Link from "next/link";
import { notFound } from "next/navigation";
import { api, fmtDate, fmtTime, pct } from "@/lib/api";
import type { Entry, RaceDetail } from "@/lib/types";

export const revalidate = 300;

function ensembleOf(entry: Entry) {
  return entry.predictions.find((p) => p.model_name === "ensemble");
}

function ExplanationList({ entry }: { entry: Entry }) {
  const pred = ensembleOf(entry);
  if (!pred || pred.explanations.length === 0) {
    return <span className="muted small">No explanations stored.</span>;
  }
  const sorted = [...pred.explanations].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
  return (
    <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
      {sorted.slice(0, 4).map((x, i) => (
        <li key={i} className={x.direction === "positive" ? "pos" : "neg"}>
          {x.direction === "positive" ? "▲" : "▼"} {x.factor}
          {x.detail ? <span className="muted"> ({x.detail})</span> : null}
        </li>
      ))}
    </ul>
  );
}

export default async function RaceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const race = await api<RaceDetail>(`/api/races/${id}`);
  if (!race) notFound();

  const entries = [...race.entries].sort((a, b) => {
    const pa = ensembleOf(a)?.predicted_rank ?? 99;
    const pb = ensembleOf(b)?.predicted_rank ?? 99;
    return pa - pb;
  });
  const anyPreds = entries.some((e) => e.predictions.length > 0);

  return (
    <>
      <h1>
        Race {race.race_no} — {race.race_name ?? race.venue}
      </h1>
      <p className="subtitle">
        {fmtDate(race.date)} {fmtTime(race.date)} · {race.venue} ·{" "}
        {race.distance_m ? `${race.distance_m}m` : "distance TBC"} ·{" "}
        {race.race_class ?? "class TBC"} · going: {race.track_condition ?? "TBC"}
        {race.weather ? ` · weather: ${race.weather}` : ""}
      </p>

      {!anyPreds ? (
        <div className="empty">
          Predictions not generated for this race yet — the pipeline runs on a schedule.
        </div>
      ) : null}

      <div className="card mt">
        <table>
          <thead>
            <tr>
              <th className="num">Pred</th>
              <th>Horse</th>
              <th>Jockey</th>
              <th>Trainer</th>
              <th className="num">Bar</th>
              <th className="num">Wt</th>
              <th className="num">Odds</th>
              <th>Win prob</th>
              <th className="num">Place</th>
              <th className="num">Conf</th>
              <th className="num">Finish</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => {
              const p = ensembleOf(e);
              return (
                <tr key={e.id} style={e.scratched ? { opacity: 0.45 } : undefined}>
                  <td className="num">
                    {p ? <span className="badge blue">#{p.predicted_rank}</span> : "–"}
                  </td>
                  <td>
                    <Link href={`/horses/${e.horse_id}`}>{e.horse_name}</Link>
                    {e.scratched ? <span className="badge red">SCR</span> : null}
                  </td>
                  <td>
                    {e.jockey_id && e.jockey_name ? (
                      <Link href={`/jockeys/${e.jockey_id}`}>{e.jockey_name}</Link>
                    ) : (
                      "–"
                    )}
                  </td>
                  <td>
                    {e.trainer_id && e.trainer_name ? (
                      <Link href={`/trainers/${e.trainer_id}`}>{e.trainer_name}</Link>
                    ) : (
                      "–"
                    )}
                  </td>
                  <td className="num">{e.barrier ?? "–"}</td>
                  <td className="num">{e.weight_kg ?? "–"}</td>
                  <td className="num">{e.odds ? e.odds.toFixed(1) : "–"}</td>
                  <td>
                    {p ? (
                      <>
                        <span className="prob-track">
                          <span
                            className="prob-bar"
                            style={{ width: `${Math.max(2, p.win_prob * 100)}%` }}
                          />
                        </span>{" "}
                        {pct(p.win_prob)}
                      </>
                    ) : (
                      "–"
                    )}
                  </td>
                  <td className="num">{p ? pct(p.place_prob) : "–"}</td>
                  <td className="num">{p?.confidence ? p.confidence.toFixed(2) : "–"}</td>
                  <td className="num">
                    {e.result?.finish_position ? (
                      <strong>{e.result.finish_position}</strong>
                    ) : e.result?.dn_category ? (
                      <span className="badge amber">{e.result.dn_category}</span>
                    ) : (
                      "–"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2>Top factors (ensemble explanations)</h2>
      <div className="grid cols-2">
        {entries.slice(0, 6).map((e) => (
          <div className="card" key={e.id}>
            <h3>
              <Link href={`/horses/${e.horse_id}`}>{e.horse_name}</Link>
            </h3>
            <ExplanationList entry={e} />
          </div>
        ))}
      </div>
    </>
  );
}
