export interface RaceSummary {
  id: number;
  date: string;
  venue: string;
  race_no: number;
  race_name: string | null;
  distance_m: number | null;
  race_class: string | null;
  track_condition: string | null;
  weather: string | null;
  status: string;
}

export interface Explanation {
  factor: string;
  direction: "positive" | "negative";
  weight: number;
  detail: string | null;
}

export interface Prediction {
  id: number;
  model_name: string;
  win_prob: number;
  place_prob: number;
  predicted_rank: number;
  confidence: number | null;
  generated_at: string | null;
  explanations: Explanation[];
}

export interface Entry {
  id: number;
  barrier: number | null;
  weight_kg: number | null;
  odds: number | null;
  scratched: boolean;
  horse_id: number;
  horse_name: string;
  jockey_id: number | null;
  jockey_name: string | null;
  trainer_id: number | null;
  trainer_name: string | null;
  result: {
    finish_position: number | null;
    margin: string | null;
    time_s: number | null;
    dn_category: string | null;
  } | null;
  predictions: Prediction[];
}

export interface RaceDetail extends RaceSummary {
  entries: Entry[];
}

export interface HorseProfile {
  id: number;
  name: string;
  sex: string | null;
  sire: string | null;
  dam: string | null;
  foaling_year: number | null;
  notes: string | null;
  career: {
    runs: number;
    wins: number;
    places: number;
    win_rate: number;
    place_rate: number;
    avg_finish: number | null;
  };
  snapshot: {
    as_of_date: string;
    form_score: number;
    days_since_last_race: number | null;
    by_distance: Record<string, BucketStats> | null;
    by_track_condition: Record<string, BucketStats> | null;
  } | null;
  recent_form: FormRow[];
}

export interface BucketStats {
  runs: number;
  wins: number;
  places: number;
  win_rate: number;
  place_rate: number;
  avg_finish: number | null;
}

export interface FormRow {
  date: string | null;
  race_no: number;
  venue: string;
  distance_m: number | null;
  track_condition: string | null;
  finish_position: number | null;
  dn_category: string | null;
  odds: number | null;
  weight_kg: number | null;
  jockey_name: string | null;
  race_id: number;
}

export interface PersonProfile {
  id: number;
  name: string;
  license_no: string | null;
  stats: { rides: number; wins: number; places: number; win_rate: number; place_rate: number };
  recent: {
    date: string | null;
    race_no: number;
    horse_id: number;
    horse_name: string;
    distance_m: number | null;
    track_condition: string | null;
    finish_position: number | null;
    race_id: number;
  }[];
}

export interface HistoryRow {
  race: {
    id: number;
    date: string | null;
    venue: string;
    race_no: number;
    distance_m: number | null;
    track_condition: string | null;
  };
  top_pick_horse_id: number;
  top_pick_prob: number;
  actual_winner_horse_id: number | null;
  hit: boolean;
}

export interface LeaderboardModel {
  model_name: string;
  latest: {
    period: string;
    n_samples: number;
    accuracy: number | null;
    precision: number | null;
    recall: number | null;
    f1: number | null;
    roc_auc: number | null;
    log_loss: number | null;
    by_distance_bucket: Record<string, Slice> | null;
    by_track_condition: Record<string, Slice> | null;
    computed_at: string | null;
  } | null;
  history: unknown[];
}

export interface Slice {
  n: number;
  roc_auc: number | null;
  log_loss: number | null;
}

export interface WhatIfResult {
  race_id: number;
  context: {
    distance_m: { from: number | null; to: number | null };
    track_condition: { from: string | null; to: string | null };
  };
  picks: {
    horse_id: number;
    horse_name: string;
    base_win_prob: number;
    adjusted_win_prob: number;
    delta: number;
    rank: number;
  }[];
  method: string;
}
