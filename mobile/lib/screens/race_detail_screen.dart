/// Race detail: predictions, factors, official result and MTC extras.
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../models.dart';
import '../scope.dart';
import '../widgets.dart';
import 'horse_detail_screen.dart';

class RaceDetailScreen extends StatefulWidget {
  const RaceDetailScreen({super.key, required this.raceId});

  final int raceId;

  @override
  State<RaceDetailScreen> createState() => _RaceDetailScreenState();
}

class _RaceDetailScreenState extends State<RaceDetailScreen> {
  RaceDetail? _race;
  bool _loading = true;
  String? _error;
  bool _rankByModel = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final api = AppScope.of(context).api;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final race = await api.raceDetail(widget.raceId);
      if (!mounted) return;
      setState(() {
        _race = race;
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
    final race = _race;
    return Scaffold(
      appBar: AppBar(
        title: race == null ? const Text('Race') : Text('R${race.raceNo}'),
        actions: [
          IconButton(
            tooltip: _rankByModel ? 'Showing model order' : 'Showing card order',
            icon: Icon(_rankByModel ? Icons.sort : Icons.format_list_numbered),
            onPressed: () => setState(() => _rankByModel = !_rankByModel),
          ),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return PlaceholderMessage(
        icon: Icons.cloud_off,
        title: 'Cannot load this race',
        message: _error,
        onRetry: _load,
      );
    }
    final race = _race;
    if (race == null) {
      return const PlaceholderMessage(icon: Icons.help_outline, title: 'Race not found');
    }

    final theme = Theme.of(context);
    final runners = _rankByModel ? race.byPrediction : race.entries;
    final pick = race.topPick;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
        children: [
          Text(
            race.raceName ?? race.venue,
            style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            [
              fmtDate(race.date),
              raceTime(race.raceTimeLabel, race.date),
              race.venue,
              if (race.distanceM != null) '${race.distanceM}m',
              if (race.raceClass != null) race.raceClass,
              if (race.trackCondition != null) race.trackCondition,
              if (race.prize != null) race.prize,
            ].join('  ·  '),
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          if (!race.hasPredictions)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'Predictions have not been generated for this race yet — the '
                'pipeline runs on a schedule.',
              ),
            ),
          if (pick != null)
            SectionCard(
              title: 'Model top pick',
              child: RunnerRow(entry: pick, onTap: () => _openHorse(pick.horseId)),
            ),
          SectionCard(
            title: _rankByModel ? 'Runners (model order)' : 'Race card',
            child: Column(
              children: [
                for (final entry in runners)
                  RunnerRow(entry: entry, onTap: () => _openHorse(entry.horseId)),
              ],
            ),
          ),
          ..._extras(race, pick, theme),
        ],
      ),
    );
  }

  /// Explanations, sectionals and the tote dividend ladder (MTC extras).
  List<Widget> _extras(RaceDetail race, Entry? pick, ThemeData theme) {
    final widgets = <Widget>[];

    final prediction = pick?.ensemble;
    if (prediction != null && prediction.explanations.isNotEmpty) {
      widgets.add(
        SectionCard(
          title: 'Why ${pick!.horseName}?',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final factor in prediction.explanations)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        factor.isPositive ? Icons.arrow_upward : Icons.arrow_downward,
                        size: 16,
                        color: factor.isPositive
                            ? Colors.green.shade600
                            : theme.colorScheme.error,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          factor.detail == null
                              ? factor.factor
                              : '${factor.factor} (${factor.detail})',
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      );
    }

    if (race.sectionalTimes.isNotEmpty) {
      final marks = race.sectionalTimes.keys.toList()
        ..sort((a, b) => (int.tryParse(b.replaceAll('m', '')) ?? 0)
            .compareTo(int.tryParse(a.replaceAll('m', '')) ?? 0));
      widgets.add(
        SectionCard(
          title: 'Sectional times',
          child: Wrap(
            spacing: 14,
            runSpacing: 4,
            children: [
              for (final mark in marks)
                Text(
                  '$mark ${race.sectionalTimes[mark]!.toStringAsFixed(2)}s',
                  style: theme.textTheme.bodySmall,
                ),
            ],
          ),
        ),
      );
    }

    if (race.toteDividends.isNotEmpty) {
      widgets.add(
        SectionCard(
          title: 'Tote dividends',
          child: Column(
            children: [
              for (final pool in race.toteDividends.keys)
                for (final selection in race.toteDividends[pool]!.keys)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 1),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 92,
                          child: Text(pool, style: theme.textTheme.bodySmall),
                        ),
                        Expanded(
                          child: Text(selection, style: theme.textTheme.bodySmall),
                        ),
                        Text(
                          race.toteDividends[pool]![selection]!.toStringAsFixed(2),
                          style: theme.textTheme.bodySmall
                              ?.copyWith(fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
            ],
          ),
        ),
      );
    }

    return widgets;
  }

  void _openHorse(int horseId) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => HorseDetailScreen(horseId: horseId)),
    );
  }
}