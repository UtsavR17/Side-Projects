import Link from "next/link";
import { notFound } from "next/navigation";
import { api, fmtDate, pct } from "@/lib/api";
import type { BucketStats, HorseProfile } from "@/lib/types";

export const revalidate = 300;

function BucketTable({ title, data }: { title: string; data: Record<string, BucketStats> }) {
  const keys = Object.keys(data ?? {}).sort();
  if (keys.length === 0) return null;
  return (
    <div className="card">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>Bucket</th>
            <th className="num">Runs</th>
            <th className="num">Wins</th>
            <th className="num">Win %</th>
            <th className="num">Place %</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const s = data[k];
            return (
              <tr key={k}>
                <td>{k}</td>
                <td className="num">{s.runs}</td>
                <td className="num">{s.wins}</td>
                <td className="num">{pct(s.win_rate, 0)}</td>
                <td className="num">{pct(s.place_rate, 0)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default async function HorsePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const horse = await api<HorseProfile>(`/api/horses/${id}`);
  if (!horse) notFound();

  const c = horse.career;

  return (
    <>
      <h1>
        {horse.name}{" "}
        {horse.sex ? <span className="badge">{horse.sex}</span> : null}
      </h1>
      <p className="subtitle">
        {horse.sire ? `by ${horse.sire}` : ""}
        {horse.dam ? ` out of ${horse.dam}` : ""}
        {horse.foaling_year ? ` · foaled ${horse.foaling_year}` : ""}
      </p>

      <div className="grid cols-3">
        <div className="card stat">
          <div className="value">{c.runs}</div>
          <div className="label">Runs</div>
        </div>
        <div className="card stat">
          <div className="value">{pct(c.win_rate, 0)}</div>
          <div className="label">Win rate</div>
        </div>
        <div className="card stat">
          <div className="value">{pct(c.place_rate, 0)}</div>
          <div className="label">Place rate</div>
        </div>
      </div>

      {horse.snapshot ? (
        <div className="grid cols-2 mt">
          <div className="card stat">
            <div className="value">{horse.snapshot.form_score.toFixed(1)}</div>
            <div className="label">
              Form score (as of {horse.snapshot.as_of_date})
            </div>
          </div>
          <div className="card stat">
            <div className="value">{horse.snapshot.days_since_last_race ?? "–"}</div>
            <div className="label">Days since last race</div>
          </div>
        </div>
      ) : null}

      <div className="grid cols-2 mt">
        <BucketTable
          title="Performance by distance"
          data={horse.snapshot?.by_distance ?? {}}
        />
        <BucketTable
          title="Performance by track condition"
          data={horse.snapshot?.by_track_condition ?? {}}
        />
      </div>

      <h2>Recent form</h2>
      {horse.recent_form.length === 0 ? (
        <div className="empty">No recorded runs yet.</div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">R</th>
                <th className="num">Dist</th>
                <th>Going</th>
                <th>Jockey</th>
                <th className="num">Odds</th>
                <th className="num">Finish</th>
              </tr>
            </thead>
            <tbody>
              {horse.recent_form.map((f, i) => (
                <tr key={i}>
                  <td>
                    <Link href={`/races/${f.race_id}`}>{fmtDate(f.date)}</Link>
                  </td>
                  <td className="num">{f.race_no}</td>
                  <td className="num">{f.distance_m ? `${f.distance_m}m` : "–"}</td>
                  <td>{f.track_condition ?? "–"}</td>
                  <td>{f.jockey_name ?? "–"}</td>
                  <td className="num">{f.odds ? f.odds.toFixed(1) : "–"}</td>
                  <td className="num">
                    {f.finish_position ? (
                      <strong>{f.finish_position}</strong>
                    ) : (
                      f.dn_category ?? "–"
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
