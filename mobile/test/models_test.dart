/// Model + formatting tests (no network, no widgets needed).
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:formedge_mobile/format.dart';
import 'package:formedge_mobile/models.dart';

/// A payload shaped exactly like the backend's race detail for the real MTC
/// race (Meeting 16, 19 Sep 2026) captured by the importers.
const _raceJson = <String, dynamic>{
  'id': 1,
  'date': '2026-09-19T12:30:00',
  'venue': 'Champ de Mars',
  'race_no': 1,
  'race_name': 'The Great Gusto - Red Star Trophy',
  'distance_m': 1400,
  'race_class': '0-25',
  'track_condition': 'good',
  'status': 'completed',
  'meeting_no': 16,
  'race_time_label': '12:30',
  'prize': 'Rs 188000',
  'win_time_s': 84.88,
  'tote_dividends': {
    'Win': {'1': 20.0},
    'Place': {'1': 11.0, '3': 19.0},
    'Exacta': {'1-3': 122.0},
  },
  'sectional_times': {'1000m': 59.21, '400m': 26.93},
  'entries': [
    {
      'id': 10,
      'saddle_no': 1,
      'barrier': 3,
      'weight_kg': 61.5,
      'sp_odds': 20.0,
      'rating': 26,
      'gear': 'XNA',
      'body_weight_kg': 465.0,
      'scratched': false,
      'horse_id': 31,
      'horse_name': 'FLAG CHAMP',
      'horse_external_id': '2298678',
      'jockey_name': 'S RAMA',
      'trainer_name': 'V RUHEE',
      'result': {
        'finish_position': 1,
        'margin': '0.8',
        'time_s': 84.88,
        'sp_odds': 20.0,
        'win_dividend': 20.0,
        'place_dividend': 11.0,
      },
      'predictions': [
        {
          'id': 1,
          'model_name': 'ensemble',
          'win_prob': 0.4124,
          'place_prob': 0.6295,
          'predicted_rank': 1,
          'confidence': 0.163,
          'explanations': [
            {
              'factor': 'official rating',
              'direction': 'positive',
              'weight': 0.31,
              'detail': '26.00 vs avg 21.00',
            },
            {
              'factor': 'days since last race',
              'direction': 'negative',
              'weight': -0.08,
              'detail': '96.00 vs avg 33.00',
            },
          ],
        },
      ],
    },
    {
      'id': 11,
      'saddle_no': 6,
      'barrier': 1,
      'weight_kg': 57.5,
      'sp_odds': 109.0,
      'rating': 18,
      'gear': 'SN *',
      'body_weight_kg': 519.0,
      'body_weight_delta': 2.0,
      'scratched': false,
      'horse_id': 32,
      'horse_name': 'BALOUCHI',
      'jockey_name': 'B ECROIGNARD',
      'trainer_name': 'A SEWDYAL',
      'notes': 'jockey claim -4.0kg',
      'result': {'finish_position': 3, 'margin': '3', 'time_s': 85.42},
      'predictions': [],
    },
  ],
};

void main() {
  group('RaceDetail parsing', () {
    test('reads race meta and official extras', () {
      final race = RaceDetail.fromJson(_raceJson);

      expect(race.meetingNo, 16);
      expect(race.raceTimeLabel, '12:30');
      expect(race.prize, 'Rs 188000');
      expect(race.winTimeS, closeTo(84.88, 0.001));
      expect(race.toteDividends['Exacta']!['1-3'], 122.0);
      expect(race.sectionalTimes['400m'], 26.93);
      expect(race.entries.length, 2);
    });

    test('reads official runner fields', () {
      final race = RaceDetail.fromJson(_raceJson);
      final winner = race.entries.first;

      expect(winner.saddleNo, 1);
      expect(winner.horseName, 'FLAG CHAMP');
      expect(winner.horseExternalId, '2298678');
      expect(winner.rating, 26);
      expect(winner.gear, 'XNA');
      expect(winner.bodyWeightKg, 465.0);
      expect(winner.result!.finishPosition, 1);
      expect(winner.result!.winDividend, 20.0);
      // SP wins over the generic odds field when both are present.
      expect(winner.displayOdds, 20.0);
    });

    test('exposes the ensemble prediction, rank order and top pick', () {
      final race = RaceDetail.fromJson(_raceJson);

      expect(race.hasPredictions, isTrue);
      expect(race.topPick!.horseName, 'FLAG CHAMP');
      expect(race.byPrediction.first.ensemble!.predictedRank, 1);
      // BALOUCHI has no prediction, so it sorts last.
      expect(race.byPrediction.last.horseName, 'BALOUCHI');

      final factors = race.topPick!.ensemble!.explanations;
      expect(factors.length, 2);
      expect(factors.first.isPositive, isTrue);
      expect(factors.last.isPositive, isFalse);
    });

    test('tolerates a payload without official fields (older cache)', () {
      final sparse = RaceDetail.fromJson(const {
        'id': 7,
        'date': '2026-01-01T14:00:00',
        'venue': 'Champ de Mars',
        'race_no': 2,
        'status': 'scheduled',
        'entries': [
          {'id': 1, 'horse_id': 5, 'horse_name': 'X', 'scratched': false},
        ],
      });

      expect(sparse.toteDividends, isEmpty);
      expect(sparse.sectionalTimes, isEmpty);
      expect(sparse.entries.single.rating, isNull);
      expect(sparse.entries.single.displayOdds, isNull);
      expect(sparse.hasPredictions, isFalse);
      expect(sparse.topPick, isNull);
    });
  });

  group('format helpers', () {
    test('percentages and one-decimal numbers', () {
      expect(pct(0.2841), '28.4%');
      expect(pct(0.875, digits: 0), '88%');
      expect(pct(null), '-');
      expect(num1(61.5), '61.5');
      expect(num1(465.0), '465');
      expect(num1(null), '-');
    });

    test('dates, race times and seconds', () {
      expect(fmtDate('2026-09-19T12:30:00'), 'Sat 19 Sep 2026');
      expect(fmtDate(null), '-');
      expect(raceTime('12:30', '2026-09-19T14:00:00'), '12:30');
      expect(raceTime(null, '2026-09-19T14:05:00'), '14:05');
      expect(raceTimeOfDay(84.88), '1:24.88');
      expect(raceTimeOfDay(null), '-');
    });
  });
}