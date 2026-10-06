/// Horse profile: career, form, ratings, body weights and distance/going splits.
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../models.dart';
import '../scope.dart';
import '../widgets.dart';

class HorseDetailScreen extends StatefulWidget {
  const HorseDetailScreen({super.key, required this.horseId});

  final int horseId;

  @override
  State<HorseDetailScreen> createState() => _HorseDetailScreenState();
}

class _HorseDetailScreenState extends State<HorseDetailScreen> {
  HorseProfile? _horse;
  bool _loading = true;
  String? _error;
  bool _following = false;
  String? _actionMessage;

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
      final horse = await api.horseProfile(widget.horseId);
      if (!mounted) return;
      setState(() {
        _horse = horse;
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

  Future<void> _toggleFollow() async {
    final state = AppScope.of(context);
    if (!state.signedIn) {
      setState(() => _actionMessage = 'Sign in from Settings to follow horses.');
      return;
    }
    try {
      final following = _following
          ? await state.api.unfollowHorse(widget.horseId)
          : await state.api.followHorse(widget.horseId);
      if (!mounted) return;
      setState(() {
        _following = following;
        _actionMessage = following ? 'Following — you will get alerts.' : 'Unfollowed.';
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _actionMessage = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final horse = _horse;
    return Scaffold(
      appBar: AppBar(
        title: Text(horse?.name ?? 'Horse'),
        actions: [
          IconButton(
            tooltip: _following ? 'Unfollow' : 'Follow',
            icon: Icon(_following ? Icons.star : Icons.star_border),
            onPressed: _toggleFollow,
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
        title: 'Cannot load this horse',
        message: _error,
        onRetry: _load,
      );
    }
    final horse = _horse;
    if (horse == null) {
      return const PlaceholderMessage(icon: Icons.help_outline, title: 'Horse not found');
    }

    final theme = Theme.of(context);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
        children: [
          Text(
            [
              if (horse.sex != null) horse.sex!,
              if (horse.foalingYear != null) 'foaled ${horse.foalingYear}',
              if (horse.sire != null) 'by ${horse.sire}',
              if (horse.externalId != null) 'MTC ${horse.externalId}',
            ].join('  ·  '),
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          if (_actionMessage != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(_actionMessage!, style: theme.textTheme.bodySmall),
            ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: StatTile(label: 'Runs', value: '${horse.runs}')),
              const SizedBox(width: 8),
              Expanded(child: StatTile(label: 'Wins', value: '${horse.wins}')),
              const SizedBox(width: 8),
              Expanded(
                child: StatTile(label: 'Win rate', value: pct(horse.winRate, digits: 0)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: StatTile(label: 'Places', value: '${horse.places}')),
              const SizedBox(width: 8),
              Expanded(
                child: StatTile(label: 'Place rate', value: pct(horse.placeRate, digits: 0)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: StatTile(
                  label: 'Form score',
                  value:
                      horse.formScore == null ? '-' : horse.formScore!.toStringAsFixed(1),
                ),
              ),
            ],
          ),
          ..._buckets('By distance', horse.byDistance, theme),
          ..._buckets('By track condition', horse.byTrackCondition, theme),
          ..._recentForm(horse, theme),
        ],
      ),
    );
  }

  /// Recent runs, including the official fields when the importers captured them.
  List<Widget> _recentForm(HorseProfile horse, ThemeData theme) {
    if (horse.recentForm.isEmpty) {
      return const [
        SectionCard(title: 'Recent form', child: Text('No recorded runs yet.')),
      ];
    }
    return [
      SectionCard(
        title: 'Recent form',
        child: Column(
          children: [
            for (final run in horse.recentForm)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 88,
                      child: Text(fmtDate(run.date), style: theme.textTheme.bodySmall),
                    ),
                    Expanded(
                      child: Text(
                        [
                          'R${run.raceNo}',
                          if (run.distanceM != null) '${run.distanceM}m',
                          if (run.trackCondition != null) run.trackCondition!,
                          if (run.jockeyName != null) run.jockeyName!,
                          if (run.rating != null) 'Rtg ${run.rating}',
                          if (run.gear != null) run.gear!,
                          if (run.bodyWeightKg != null) 'Hwt ${num1(run.bodyWeightKg)}',
                          if (run.displayOdds != null) '@${num1(run.displayOdds)}',
                        ].join('  ·  '),
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                    Text(
                      run.finishPosition != null
                          ? '${run.finishPosition}'
                          : (run.dnCategory ?? '-'),
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    ];
  }

  /// Distance / going breakdown from the precomputed form snapshot.
  List<Widget> _buckets(
    String title,
    Map<String, Map<String, dynamic>> buckets,
    ThemeData theme,
  ) {
    if (buckets.isEmpty) return const [];
    final keys = buckets.keys.toList()..sort();
    return [
      SectionCard(
        title: title,
        child: Column(
          children: [
            for (final key in keys)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    SizedBox(
                      width: 108,
                      child: Text(key, style: theme.textTheme.bodySmall),
                    ),
                    Expanded(
                      child: Text(
                        '${buckets[key]!['runs'] ?? 0} runs  ·  '
                        '${pct((buckets[key]!['win_rate'] as num?)?.toDouble(), digits: 0)} win',
                        style: theme.textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    ];
  }
}