/// Typed models mirroring the FormEdge REST payloads.
///
/// Everything tolerates missing keys: the backend adds fields over time (e.g.
/// the official MTC ratings/dividends) and older cached payloads must still
/// decode instead of crashing the app.
library;

double? _d(Object? value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

int? _i(Object? value) {
  if (value == null) return null;
  if (value is num) return value.toInt();
  return int.tryParse(value.toString());
}

String? _s(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

List<Map<String, dynamic>> _maps(Object? value) {
  if (value is! List) return const [];
  return value.whereType<Map<String, dynamic>>().toList(growable: false);
}

/// Horse or jockey/trainer listing entry.
class NameId {
  NameId({required this.id, required this.name});

  factory NameId.fromJson(Map<String, dynamic> json) =>
      NameId(id: _i(json['id']) ?? 0, name: _s(json['name']) ?? '?');

  final int id;
  final String name;
}

class RaceSummary {
  RaceSummary({
    required this.id,
    required this.date,
    required this.venue,
    required this.raceNo,
    this.raceName,
    this.distanceM,
    this.raceClass,
    this.trackCondition,
    this.weather,
    required this.status,
    this.meetingNo,
    this.raceTimeLabel,
    this.prize,
    this.winTimeS,
  });

  factory RaceSummary.fromJson(Map<String, dynamic> json) => RaceSummary(
        id: _i(json['id']) ?? 0,
        date: _s(json['date']) ?? '',
        venue: _s(json['venue']) ?? '',
        raceNo: _i(json['race_no']) ?? 0,
        raceName: _s(json['race_name']),
        distanceM: _i(json['distance_m']),
        raceClass: _s(json['race_class']),
        trackCondition: _s(json['track_condition']),
        weather: _s(json['weather']),
        status: _s(json['status']) ?? 'scheduled',
        meetingNo: _i(json['meeting_no']),
        raceTimeLabel: _s(json['race_time_label']),
        prize: _s(json['prize']),
        winTimeS: _d(json['win_time_s']),
      );

  final int id;
  final String date;
  final String venue;
  final int raceNo;
  final String? raceName;
  final int? distanceM;
  final String? raceClass;
  final String? trackCondition;
  final String? weather;
  final String status;
  final int? meetingNo;
  final String? raceTimeLabel;
  final String? prize;
  final double? winTimeS;

  bool get isCompleted => status == 'completed';
}

class Explanation {
  Explanation({
    required this.factor,
    required this.direction,
    required this.weight,
    this.detail,
  });

  factory Explanation.fromJson(Map<String, dynamic> json) => Explanation(
        factor: _s(json['factor']) ?? '?',
        direction: _s(json['direction']) ?? 'positive',
        weight: _d(json['weight']) ?? 0,
        detail: _s(json['detail']),
      );

  final String factor;
  final String direction;
  final double weight;
  final String? detail;

  bool get isPositive => direction == 'positive';
}

class Prediction {
  Prediction({
    required this.id,
    required this.modelName,
    required this.winProb,
    required this.placeProb,
    required this.predictedRank,
    this.confidence,
    required this.explanations,
  });

  factory Prediction.fromJson(Map<String, dynamic> json) => Prediction(
        id: _i(json['id']) ?? 0,
        modelName: _s(json['model_name']) ?? '?',
        winProb: _d(json['win_prob']) ?? 0,
        placeProb: _d(json['place_prob']) ?? 0,
        predictedRank: _i(json['predicted_rank']) ?? 0,
        confidence: _d(json['confidence']),
        explanations: _maps(json['explanations'])
            .map(Explanation.fromJson)
            .toList(growable: false),
      );

  final int id;
  final String modelName;
  final double winProb;
  final double placeProb;
  final int predictedRank;
  final double? confidence;
  final List<Explanation> explanations;

  bool get isEnsemble => modelName == 'ensemble';
}

class RunResult {
  RunResult({
    this.finishPosition,
    this.margin,
    this.timeS,
    this.spOdds,
    this.winDividend,
    this.placeDividend,
    this.dnCategory,
  });

  factory RunResult.fromJson(Map<String, dynamic> json) => RunResult(
        finishPosition: _i(json['finish_position']),
        margin: _s(json['margin']),
        timeS: _d(json['time_s']),
        spOdds: _d(json['sp_odds']),
        winDividend: _d(json['win_dividend']),
        placeDividend: _d(json['place_dividend']),
        dnCategory: _s(json['dn_category']),
      );

  final int? finishPosition;
  final String? margin;
  final double? timeS;
  final double? spOdds;
  final double? winDividend;
  final double? placeDividend;
  final String? dnCategory;
}

class Entry {
  Entry({
    required this.id,
    this.saddleNo,
    this.barrier,
    this.weightKg,
    this.odds,
    this.spOdds,
    this.rating,
    this.gear,
    this.bodyWeightKg,
    this.bodyWeightDelta,
    required this.scratched,
    this.notes,
    required this.horseId,
    required this.horseName,
    this.horseExternalId,
    this.jockeyId,
    this.jockeyName,
    this.trainerId,
    this.trainerName,
    this.result,
    required this.predictions,
  });

  factory Entry.fromJson(Map<String, dynamic> json) {
    final result = json['result'];
    return Entry(
      id: _i(json['id']) ?? 0,
      saddleNo: _i(json['saddle_no']),
      barrier: _i(json['barrier']),
      weightKg: _d(json['weight_kg']),
      odds: _d(json['odds']),
      spOdds: _d(json['sp_odds']),
      rating: _i(json['rating']),
      gear: _s(json['gear']),
      bodyWeightKg: _d(json['body_weight_kg']),
      bodyWeightDelta: _d(json['body_weight_delta']),
      scratched: json['scratched'] == true,
      notes: _s(json['notes']),
      horseId: _i(json['horse_id']) ?? 0,
      horseName: _s(json['horse_name']) ?? '?',
      horseExternalId: _s(json['horse_external_id']),
      jockeyId: _i(json['jockey_id']),
      jockeyName: _s(json['jockey_name']),
      trainerId: _i(json['trainer_id']),
      trainerName: _s(json['trainer_name']),
      result: result is Map<String, dynamic> ? RunResult.fromJson(result) : null,
      predictions: _maps(json['predictions'])
          .map(Prediction.fromJson)
          .toList(growable: false),
    );
  }

  final int id;
  final int? saddleNo;
  final int? barrier;
  final double? weightKg;
  final double? odds;
  final double? spOdds;
  final int? rating;
  final String? gear;
  final double? bodyWeightKg;
  final double? bodyWeightDelta;
  final bool scratched;
  final String? notes;
  final int horseId;
  final String horseName;
  final String? horseExternalId;
  final int? jockeyId;
  final String? jockeyName;
  final int? trainerId;
  final String? trainerName;
  final RunResult? result;
  final List<Prediction> predictions;

  /// The ensemble prediction, when the pipeline has produced one.
  Prediction? get ensemble {
    for (final prediction in predictions) {
      if (prediction.isEnsemble) return prediction;
    }
    return null;
  }

  /// Price to show: the official SP first, then any stored odds.
  double? get displayOdds => result?.spOdds ?? spOdds ?? odds;
}

class RaceDetail extends RaceSummary {
  RaceDetail({
    required super.id,
    required super.date,
    required super.venue,
    required super.raceNo,
    super.raceName,
    super.distanceM,
    super.raceClass,
    super.trackCondition,
    super.weather,
    required super.status,
    super.meetingNo,
    super.raceTimeLabel,
    super.prize,
    super.winTimeS,
    required this.entries,
    required this.toteDividends,
    required this.sectionalTimes,
  });

  factory RaceDetail.fromJson(Map<String, dynamic> json) {
    final dividends = <String, Map<String, double>>{};
    final rawDividends = json['tote_dividends'];
    if (rawDividends is Map<String, dynamic>) {
      rawDividends.forEach((pool, selections) {
        final parsed = <String, double>{};
        if (selections is Map<String, dynamic>) {
          selections.forEach((selection, amount) {
            final value = _d(amount);
            if (value != null) parsed[selection] = value;
          });
        }
        if (parsed.isNotEmpty) dividends[pool] = parsed;
      });
    }
    final sectionals = <String, double>{};
    final rawSectionals = json['sectional_times'];
    if (rawSectionals is Map<String, dynamic>) {
      rawSectionals.forEach((mark, seconds) {
        final value = _d(seconds);
        if (value != null) sectionals[mark] = value;
      });
    }
    return RaceDetail(
      id: _i(json['id']) ?? 0,
      date: _s(json['date']) ?? '',
      venue: _s(json['venue']) ?? '',
      raceNo: _i(json['race_no']) ?? 0,
      raceName: _s(json['race_name']),
      distanceM: _i(json['distance_m']),
      raceClass: _s(json['race_class']),
      trackCondition: _s(json['track_condition']),
      weather: _s(json['weather']),
      status: _s(json['status']) ?? 'scheduled',
      meetingNo: _i(json['meeting_no']),
      raceTimeLabel: _s(json['race_time_label']),
      prize: _s(json['prize']),
      winTimeS: _d(json['win_time_s']),
      entries: _maps(json['entries']).map(Entry.fromJson).toList(growable: false),
      toteDividends: dividends,
      sectionalTimes: sectionals,
    );
  }

  final List<Entry> entries;
  final Map<String, Map<String, double>> toteDividends;
  final Map<String, double> sectionalTimes;

  bool get hasPredictions => entries.any((e) => e.ensemble != null);

  /// Runners ordered by the model's view (unranked runners last).
  List<Entry> get byPrediction {
    final ranked = [...entries];
    ranked.sort((a, b) =>
        (a.ensemble?.predictedRank ?? 99).compareTo(b.ensemble?.predictedRank ?? 99));
    return ranked;
  }

  /// Top pick per the stored ensemble, if the pipeline produced one.
  Entry? get topPick {
    final withPredictions = entries.where((e) => e.ensemble != null).toList();
    if (withPredictions.isEmpty) return null;
    withPredictions.sort(
      (a, b) => a.ensemble!.predictedRank.compareTo(b.ensemble!.predictedRank),
    );
    return withPredictions.first;
  }
}

class FormRow {
  FormRow({
    this.date,
    required this.raceNo,
    required this.venue,
    this.distanceM,
    this.trackCondition,
    this.finishPosition,
    this.dnCategory,
    this.odds,
    this.spOdds,
    this.weightKg,
    this.rating,
    this.gear,
    this.bodyWeightKg,
    this.bodyWeightDelta,
    this.barrier,
    this.jockeyName,
    required this.raceId,
  });

  factory FormRow.fromJson(Map<String, dynamic> json) => FormRow(
        date: _s(json['date']),
        raceNo: _i(json['race_no']) ?? 0,
        venue: _s(json['venue']) ?? '',
        distanceM: _i(json['distance_m']),
        trackCondition: _s(json['track_condition']),
        finishPosition: _i(json['finish_position']),
        dnCategory: _s(json['dn_category']),
        odds: _d(json['odds']),
        spOdds: _d(json['sp_odds']),
        weightKg: _d(json['weight_kg']),
        rating: _i(json['rating']),
        gear: _s(json['gear']),
        bodyWeightKg: _d(json['body_weight_kg']),
        bodyWeightDelta: _d(json['body_weight_delta']),
        barrier: _i(json['barrier']),
        jockeyName: _s(json['jockey_name']),
        raceId: _i(json['race_id']) ?? 0,
      );

  final String? date;
  final int raceNo;
  final String venue;
  final int? distanceM;
  final String? trackCondition;
  final int? finishPosition;
  final String? dnCategory;
  final double? odds;
  final double? spOdds;
  final double? weightKg;
  final int? rating;
  final String? gear;
  final double? bodyWeightKg;
  final double? bodyWeightDelta;
  final int? barrier;
  final String? jockeyName;
  final int raceId;

  double? get displayOdds => spOdds ?? odds;
}

class HorseProfile {
  HorseProfile({
    required this.id,
    required this.name,
    this.externalId,
    this.sex,
    this.sire,
    this.dam,
    this.foalingYear,
    this.notes,
    required this.runs,
    required this.wins,
    required this.places,
    required this.winRate,
    required this.placeRate,
    this.avgFinish,
    this.formScore,
    this.daysSinceLastRace,
    required this.byDistance,
    required this.byTrackCondition,
    required this.recentForm,
  });

  factory HorseProfile.fromJson(Map<String, dynamic> json) {
    final career = json['career'] is Map<String, dynamic>
        ? json['career'] as Map<String, dynamic>
        : const <String, dynamic>{};
    final snapshot = json['snapshot'] is Map<String, dynamic>
        ? json['snapshot'] as Map<String, dynamic>
        : const <String, dynamic>{};

    Map<String, Map<String, dynamic>> buckets(Object? raw) {
      final out = <String, Map<String, dynamic>>{};
      if (raw is Map<String, dynamic>) {
        raw.forEach((key, value) {
          if (value is Map<String, dynamic>) out[key] = value;
        });
      }
      return out;
    }

    return HorseProfile(
      id: _i(json['id']) ?? 0,
      name: _s(json['name']) ?? '?',
      externalId: _s(json['external_id']),
      sex: _s(json['sex']),
      sire: _s(json['sire']),
      dam: _s(json['dam']),
      foalingYear: _i(json['foaling_year']),
      notes: _s(json['notes']),
      runs: _i(career['runs']) ?? 0,
      wins: _i(career['wins']) ?? 0,
      places: _i(career['places']) ?? 0,
      winRate: _d(career['win_rate']) ?? 0,
      placeRate: _d(career['place_rate']) ?? 0,
      avgFinish: _d(career['avg_finish']),
      formScore: _d(snapshot['form_score']),
      daysSinceLastRace: _i(snapshot['days_since_last_race']),
      byDistance: buckets(snapshot['by_distance']),
      byTrackCondition: buckets(snapshot['by_track_condition']),
      recentForm: _maps(json['recent_form']).map(FormRow.fromJson).toList(growable: false),
    );
  }

  final int id;
  final String name;
  final String? externalId;
  final String? sex;
  final String? sire;
  final String? dam;
  final int? foalingYear;
  final String? notes;
  final int runs;
  final int wins;
  final int places;
  final double winRate;
  final double placeRate;
  final double? avgFinish;
  final double? formScore;
  final int? daysSinceLastRace;
  final Map<String, Map<String, dynamic>> byDistance;
  final Map<String, Map<String, dynamic>> byTrackCondition;
  final List<FormRow> recentForm;
}

class HistoryRow {
  HistoryRow({
    required this.raceId,
    this.date,
    required this.raceNo,
    this.distanceM,
    this.trackCondition,
    required this.topPickHorseId,
    required this.topPickProb,
    this.actualWinnerHorseId,
    required this.hit,
  });

  factory HistoryRow.fromJson(Map<String, dynamic> json) {
    final race = json['race'] is Map<String, dynamic>
        ? json['race'] as Map<String, dynamic>
        : const <String, dynamic>{};
    return HistoryRow(
      raceId: _i(race['id']) ?? 0,
      date: _s(race['date']),
      raceNo: _i(race['race_no']) ?? 0,
      distanceM: _i(race['distance_m']),
      trackCondition: _s(race['track_condition']),
      topPickHorseId: _i(json['top_pick_horse_id']) ?? 0,
      topPickProb: _d(json['top_pick_prob']) ?? 0,
      actualWinnerHorseId: _i(json['actual_winner_horse_id']),
      hit: json['hit'] == true,
    );
  }

  final int raceId;
  final String? date;
  final int raceNo;
  final int? distanceM;
  final String? trackCondition;
  final int topPickHorseId;
  final double topPickProb;
  final int? actualWinnerHorseId;
  final bool hit;
}

class PredictionHistory {
  PredictionHistory({required this.rows});

  factory PredictionHistory.fromJson(Map<String, dynamic> json) => PredictionHistory(
        rows: _maps(json['history']).map(HistoryRow.fromJson).toList(growable: false),
      );

  final List<HistoryRow> rows;

  int get hits => rows.where((r) => r.hit).length;
  double? get hitRate => rows.isEmpty ? null : hits / rows.length;
}

class ModelScore {
  ModelScore({
    required this.modelName,
    this.period,
    this.accuracy,
    this.rocAuc,
    this.nSamples,
  });

  factory ModelScore.fromJson(Map<String, dynamic> json) {
    final latest = json['latest'] is Map<String, dynamic>
        ? json['latest'] as Map<String, dynamic>
        : const <String, dynamic>{};
    return ModelScore(
      modelName: _s(json['model_name']) ?? '?',
      period: _s(latest['period']),
      accuracy: _d(latest['accuracy']),
      rocAuc: _d(latest['roc_auc']),
      nSamples: _i(latest['n_samples']),
    );
  }

  final String modelName;
  final String? period;
  final double? accuracy;
  final double? rocAuc;
  final int? nSamples;
}

class Leaderboard {
  Leaderboard({required this.models});

  factory Leaderboard.fromJson(Map<String, dynamic> json) => Leaderboard(
        models: _maps(json['models']).map(ModelScore.fromJson).toList(growable: false),
      );

  final List<ModelScore> models;

  ModelScore? get ensemble {
    for (final model in models) {
      if (model.modelName == 'ensemble') return model;
    }
    return null;
  }
}

class AppNotification {
  AppNotification({
    required this.id,
    required this.category,
    required this.title,
    this.body,
    required this.isRead,
    this.createdAt,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        id: _i(json['id']) ?? 0,
        category: _s(json['category']) ?? 'general',
        title: _s(json['title']) ?? '',
        body: _s(json['body']),
        isRead: json['is_read'] == true,
        createdAt: _s(json['created_at']),
      );

  final int id;
  final String category;
  final String title;
  final String? body;
  final bool isRead;
  final String? createdAt;
}

class NotificationPage {
  NotificationPage({required this.notifications, required this.unreadCount});

  factory NotificationPage.fromJson(Map<String, dynamic> json) => NotificationPage(
        notifications: _maps(json['notifications'])
            .map(AppNotification.fromJson)
            .toList(growable: false),
        unreadCount: _i(json['unread_count']) ?? 0,
      );

  final List<AppNotification> notifications;
  final int unreadCount;
}