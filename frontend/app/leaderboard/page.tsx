import { api, pct } from "@/lib/api";
import type { LeaderboardModel, Slice } from "@/lib/types";

export const revalidate = 300;

function SliceTable({ title, slices }: { title: string; slices: Record<string, Slice> | null }) {
  const keys = Object.keys(slices ?? {}).sort();
  if (keys.length === 0) return null;
  return (
    <div className="card">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>Slice</th>
            <th className="num">N</th>
            <th className="num">ROC-AUC</th>
            <th className="num">Log loss</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td>{k}</td>
              <td className="num">{slices![k].n}</td>
              <td className="num">
                {slices![k].roc_auc !== null ? slices![k].roc_auc!.toFixed(3) : "–"}
              </td>
              <td className="num">
                {slices![k].log_loss !== null ? slices![k].log_loss!.toFixed(3) : "–"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function LeaderboardPage() {
  const data = await api<{ models: LeaderboardModel[] }>("/api/leaderboard");
  const models = data?.models ?? [];

  return (
    <>
      <h1>Model leaderboard</h1>
      <p className="subtitle">
        Per-model accuracy sliced by distance bucket and track condition (§9). Ensemble
        weights adapt from these scores.
      </p>

      {models.length === 0 ? (
        <div className="empty">No model performance recorded yet — run train/evaluate.</div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Period</th>
                <th className="num">N</th>
                <th className="num">Top-1 acc</th>
                <th className="num">Precision</th>
                <th className="num">Recall</th>
                <th className="num">F1</th>
                <th className="num">ROC-AUC</th>
                <th className="num">Log loss</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => {
                const l = m.latest;
                return (
                  <tr key={m.model_name}>
                    <td>
                      <strong>{m.model_name}</strong>
                    </td>
                    <td className="small muted">{l?.period ?? "–"}</td>
                    <td className="num">{l?.n_samples ?? "–"}</td>
                    <td className="num">{pct(l?.accuracy ?? null, 1)}</td>
                    <td className="num">
                      {l?.precision !== null && l?.precision !== undefined
                        ? l.precision.toFixed(3)
                        : "–"}
                    </td>
                    <td className="num">
                      {l?.recall !== null && l?.recall !== undefined
                        ? l.recall.toFixed(3)
                        : "–"}
                    </td>
                    <td className="num">
                      {l?.f1 !== null && l?.f1 !== undefined ? l.f1.toFixed(3) : "–"}
                    </td>
                    <td className="num">
                      {l?.roc_auc !== null && l?.roc_auc !== undefined
                        ? l.roc_auc.toFixed(3)
                        : "–"}
                    </td>
                    <td className="num">
                      {l?.log_loss !== null && l?.log_loss !== undefined
                        ? l.log_loss.toFixed(3)
                        : "–"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {models.map((m) => (
        <div key={m.model_name}>
          <h2>{m.model_name} — latest slices</h2>
          <div className="grid cols-2">
            <SliceTable title="By distance bucket" slices={m.latest?.by_distance_bucket ?? null} />
            <SliceTable title="By track condition" slices={m.latest?.by_track_condition ?? null} />
          </div>
        </div>
      ))}
    </>
  );
}
