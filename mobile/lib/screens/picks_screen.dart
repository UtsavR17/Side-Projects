/// Today's top predictions, past results vs predictions, and model leaderboard.
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../models.dart';
import '../scope.dart';
import '../widgets.dart';
import 'race_detail_screen.dart';

class PicksScreen extends StatefulWidget {
  const PicksScreen({super.key});

  @override
  State<PicksScreen> createState() => _PicksScreenState();
}

class _PicksScreenState extends State<PicksScreen> {
  List<RaceDetail> _races = const [];
  PredictionHistory? _history;
  Leaderboard? _leaderboard;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load({bool forceRefresh = false}) async {
    final api = AppScope.of(context).api;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final upcoming = await api.upcomingRaces(forceRefresh: forceRefresh);
      // Only the next meeting matters for "today's picks" — keeps calls few.
      final firstDay = upcoming.isEmpty ? null : upcoming.first.date.split('T').first;
      final todays = upcoming
          .where((race) => race.date.split('T').first == firstDay)
          .take(6)
          .toList();
      final details = <RaceDetail>[];
      for (final race in todays) {
        try {
          details.add(await api.raceDetail(race.id));
        } on ApiException {
          // Skip a race that fails; the rest still render.
        }
      }
      final history = await api.predictionHistory(limit: 20);
      final leaderboard = await api.leaderboard();
      if (!mounted) return;
      setState(() {
        _races = details;
        _history = history;
        _leaderboard = leaderboard;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Today's picks"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _load(forceRefresh: true),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _load(forceRefresh: true),
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return PlaceholderMessage(
        icon: Icons.cloud_off,
        title: 'Cannot load picks',
        message: '$_error\n\nCheck the server address in Settings.',
        onRetry: () => _load(forceRefresh: true),
      );
    }

    final history = _history;
    final leaderboard = _leaderboard;
    final ensemble = leaderboard?.ensemble;
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
      children: [
        Row(
          children: [
            Expanded(
              child: StatTile(
                label: 'Recent hit rate',
                value: history?.hitRate == null ? '-' : pct(history!.hitRate),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: StatTile(
                label: 'Scored races',
                value: '${history?.rows.length ?? 0}',
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: StatTile(
                label: 'Ensemble top-1',
                value: ensemble?.accuracy == null
                    ? '-'
                    : pct(ensemble!.accuracy, digits: 0),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        if (_races.isEmpty)
          const SectionCard(
            title: 'Next meeting',
            child: Text('No upcoming races with stored predictions yet.'),
          )
        else
          for (final race in _races) _racePicks(race, theme),
        ..._historySection(history, theme),
        ..._leaderboardSection(leaderboard, theme),
      ],
    );
  }

  List<Widget> _historySection(PredictionHistory? history, ThemeData theme) {
    if (history == null || history.rows.isEmpty) return const [];
    return [
      SectionCard(
        title: 'Past results vs predictions',
        child: Column(
          children: [
            for (final row in history.rows.take(12))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    SizedBox(
                      width: 84,
                      child: Text(fmtDate(row.date), style: theme.textTheme.bodySmall),
                    ),
                    Expanded(
                      child: Text(
                        'R${row.raceNo}'
                        '${row.distanceM != null ? '  ${row.distanceM}m' : ''}'
                        '${row.trackCondition != null ? '  ${row.trackCondition}' : ''}',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                    Text(
                      'pick ${pct(row.topPickProb, digits: 0)}',
                      style: theme.textTheme.bodySmall,
                    ),
                    const SizedBox(width: 8),
                    Tag(
                      text: row.hit ? 'HIT' : 'miss',
                      color: row.hit ? Colors.green.shade600 : theme.colorScheme.error,
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    ];
  }

  List<Widget> _leaderboardSection(Leaderboard? leaderboard, ThemeData theme) {
    if (leaderboard == null || leaderboard.models.isEmpty) return const [];
    return [
      SectionCard(
        title: 'Model leaderboard',
        child: Column(
          children: [
            for (final model in leaderboard.models)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        model.modelName,
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600),
                      ),
                    ),
                    Text(
                      'top-1 ${pct(model.accuracy, digits: 0)}   '
                      'AUC ${model.rocAuc?.toStringAsFixed(3) ?? '-'}   '
                      'n=${model.nSamples ?? 0}',
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    ];
  }

  Widget _racePicks(RaceDetail race, ThemeData theme) {
    final pick = race.topPick;
    return SectionCard(
      title: 'R${race.raceNo}  ·  ${race.raceName ?? race.venue}  ·  '
          '${raceTime(race.raceTimeLabel, race.date)}',
      trailing: Text(
        [
          if (race.distanceM != null) '${race.distanceM}m',
          if (race.trackCondition != null) race.trackCondition!,
        ].join('  '),
        style: theme.textTheme.labelSmall,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (pick == null)
            const Text('No stored predictions for this race yet.')
          else ...[
            Text(
              'Top pick: ${pick.horseName}  ${pct(pick.ensemble?.winProb)}',
              style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            for (final entry in race.byPrediction.take(4))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    SizedBox(
                      width: 22,
                      child: Text(
                        '${entry.ensemble?.predictedRank ?? '-'}',
                        style: theme.textTheme.labelMedium,
                      ),
                    ),
                    Expanded(
                      child: Text(entry.horseName, style: theme.textTheme.bodySmall),
                    ),
                    ProbBar(value: entry.ensemble?.winProb ?? 0, width: 52),
                  ],
                ),
              ),
          ],
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => RaceDetailScreen(raceId: race.id),
                ),
              ),
              child: const Text('Full race'),
            ),
          ),
        ],
      ),
    );
  }
}