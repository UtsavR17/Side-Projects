"use client";

import { useEffect, useState } from "react";
import { api, apiPost, pct } from "@/lib/api";
import type { RaceSummary, WhatIfResult } from "@/lib/types";

const CONDITIONS = ["heavy", "soft", "good", "good to firm", "firm", "fast"];
const DISTANCES = [1200, 1400, 1600, 1800, 2000, 2200, 2400];

/**
 * Race simulator — calls the dedicated what-if endpoint (never a re-scrape).
 */
export default function SimulatorPage() {
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [raceId, setRaceId] = useState<number | "">("");
  const [distance, setDistance] = useState<number | "">("");
  const [condition, setCondition] = useState<string>("");
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ races: RaceSummary[] }>("/api/races").then((data) => {
      const list = data?.races ?? [];
      setRaces(list);
      if (list.length > 0) setRaceId(list[0].id);
    });
  }, []);

  async function runSimulation() {
    if (raceId === "") return;
    setLoading(true);
    setError(null);
    const body: Record<string, unknown> = { race_id: raceId };
    if (distance !== "") body.distance_m = distance;
    if (condition !== "") body.track_condition = condition;
    const data = await apiPost<WhatIfResult>("/api/simulator/what-if", body);
    setLoading(false);
    if (!data) {
      setError("Simulation failed — does this race have stored predictions yet?");
      setResult(null);
      return;
    }
    setResult(data);
  }

  return (
    <>
      <h1>Race simulator</h1>
      <p className="subtitle">
        Change the distance or going and see how the stored ensemble probabilities shift —
        a lightweight what-if, not a model re-run.
      </p>

      <div className="card">
        <div className="form-row">
          <div>
            <label>Race</label>
            <select
              value={raceId}
              onChange={(e) => setRaceId(e.target.value ? Number(e.target.value) : "")}
            >
              {races.map((r) => (
                <option key={r.id} value={r.id}>
                  R{r.race_no} · {new Date(r.date).toLocaleDateString("en-GB")} ·{" "}
                  {r.distance_m ?? "?"}m · {r.track_condition ?? "going?"}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>New distance</label>
            <select
              value={distance}
              onChange={(e) =>
                setDistance(e.target.value ? Number(e.target.value) : "")
              }
            >
              <option value="">keep</option>
              {DISTANCES.map((d) => (
                <option key={d} value={d}>
                  {d}m
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>New going</label>
            <select value={condition} onChange={(e) => setCondition(e.target.value)}>
              <option value="">keep</option>
              {CONDITIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <button onClick={runSimulation} disabled={loading || raceId === ""}>
            {loading ? "Running…" : "Simulate"}
          </button>
        </div>
        {error ? <p className="neg">{error}</p> : null}
        {races.length === 0 ? (
          <p className="muted">No upcoming races available.</p>
        ) : null}
      </div>

      {result ? (
        <>
          <h2>
            Shift: {result.context.distance_m.from ?? "?"}m →{" "}
            {result.context.distance_m.to ?? "?"}m ·{" "}
            {result.context.track_condition.from ?? "?"} →{" "}
            {result.context.track_condition.to ?? "?"}
          </h2>
          <div className="card">
            <table>
              <thead>
                <tr>
                  <th className="num">New rank</th>
                  <th>Horse</th>
                  <th className="num">Base</th>
                  <th className="num">Adjusted</th>
                  <th className="num">Δ</th>
                </tr>
              </thead>
              <tbody>
                {result.picks.map((p) => (
                  <tr key={p.horse_id}>
                    <td className="num">
                      <span className="badge blue">#{p.rank}</span>
                    </td>
                    <td>{p.horse_name}</td>
                    <td className="num">{pct(p.base_win_prob)}</td>
                    <td className="num">{pct(p.adjusted_win_prob)}</td>
                    <td className={`num ${p.delta >= 0 ? "pos" : "neg"}`}>
                      {p.delta >= 0 ? "+" : ""}
                      {(p.delta * 100).toFixed(1)}pp
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small mt">Method: {result.method}</p>
          </div>
        </>
      ) : null}
    </>
  );
}
