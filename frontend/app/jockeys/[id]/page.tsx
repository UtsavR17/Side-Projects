import Link from "next/link";
import { notFound } from "next/navigation";
import { api, fmtDate, pct } from "@/lib/api";
import type { PersonProfile } from "@/lib/types";

export const revalidate = 300;

function PersonPage({
  profile,
  kind,
}: {
  profile: PersonProfile;
  kind: "Jockey" | "Trainer";
}) {
  const s = profile.stats;
  return (
    <>
      <h1>
        {profile.name} <span className="badge blue">{kind}</span>
      </h1>
      <p className="subtitle">
        {profile.license_no ? `License ${profile.license_no}` : "No license on file"}
      </p>

      <div className="grid cols-3">
        <div className="card stat">
          <div className="value">{s.rides}</div>
          <div className="label">Rides</div>
        </div>
        <div className="card stat">
          <div className="value">{pct(s.win_rate, 0)}</div>
          <div className="label">Win rate</div>
        </div>
        <div className="card stat">
          <div className="value">{pct(s.place_rate, 0)}</div>
          <div className="label">Place rate</div>
        </div>
      </div>

      <h2>Recent runs</h2>
      {profile.recent.length === 0 ? (
        <div className="empty">No recorded runs yet.</div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">R</th>
                <th>Horse</th>
                <th className="num">Dist</th>
                <th>Going</th>
                <th className="num">Finish</th>
              </tr>
            </thead>
            <tbody>
              {profile.recent.map((r, i) => (
                <tr key={i}>
                  <td>
                    <Link href={`/races/${r.race_id}`}>{fmtDate(r.date)}</Link>
                  </td>
                  <td className="num">{r.race_no}</td>
                  <td>
                    <Link href={`/horses/${r.horse_id}`}>{r.horse_name}</Link>
                  </td>
                  <td className="num">{r.distance_m ? `${r.distance_m}m` : "–"}</td>
                  <td>{r.track_condition ?? "–"}</td>
                  <td className="num">{r.finish_position ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

async function JockeyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const profile = await api<PersonProfile>(`/api/jockeys/${id}`);
  if (!profile) notFound();
  return <PersonPage profile={profile} kind="Jockey" />;
}

export default JockeyPage;
