/// Upcoming races list (default screen).
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../models.dart';
import '../scope.dart';
import '../widgets.dart';
import 'race_detail_screen.dart';

class RacesScreen extends StatefulWidget {
  const RacesScreen({super.key});

  @override
  State<RacesScreen> createState() => _RacesScreenState();
}

class _RacesScreenState extends State<RacesScreen> {
  List<RaceSummary> _races = const [];
  bool _loading = true;
  String? _error;
  bool _showRecent = false;

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
      final races = _showRecent
          ? await api.recentRaces(forceRefresh: forceRefresh)
          : await api.upcomingRaces(forceRefresh: forceRefresh);
      if (!mounted) return;
      setState(() {
        _races = races;
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
        title: Text(_showRecent ? 'Recent meetings' : 'Upcoming races'),
        actions: [
          IconButton(
            tooltip: _showRecent ? 'Show upcoming' : 'Show recent results',
            icon: Icon(_showRecent ? Icons.upcoming : Icons.history),
            onPressed: () {
              setState(() => _showRecent = !_showRecent);
              _load(forceRefresh: true);
            },
          ),
          IconButton(
            tooltip: 'Refresh',
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
      return ListView(
        children: [
          SizedBox(
            height: 420,
            child: PlaceholderMessage(
              icon: Icons.cloud_off,
              title: 'Cannot load races',
              message: '$_error\n\nCheck the server address in Settings.',
              onRetry: () => _load(forceRefresh: true),
            ),
          ),
        ],
      );
    }
    if (_races.isEmpty) {
      return ListView(
        children: [
          SizedBox(
            height: 420,
            child: PlaceholderMessage(
              icon: Icons.event_busy,
              title: _showRecent ? 'No results yet' : 'No upcoming races',
              message: 'The pipeline fills this in after the next scrape or import.',
            ),
          ),
        ],
      );
    }

    // Group by meeting day for a readable card list.
    final byDay = <String, List<RaceSummary>>{};
    for (final race in _races) {
      final day = race.date.split('T').first;
      byDay.putIfAbsent(day, () => []).add(race);
    }

    return ListView(
      padding: const EdgeInsets.only(bottom: 24),
      children: [
        for (final day in byDay.keys)
          SectionCard(
            title: '${fmtDate(day)}  ·  ${relativeToNow(day)}',
            child: Column(
              children: [
                for (final race in byDay[day]!)
                  ListTile(
                    dense: true,
                    title: Text(
                      'R${race.raceNo}'
                      '${race.raceName != null ? '  ${race.raceName}' : ''}',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(
                      [
                        race.venue,
                        raceTime(race.raceTimeLabel, race.date),
                        if (race.distanceM != null) '${race.distanceM}m',
                        if (race.raceClass != null) race.raceClass,
                        if (race.trackCondition != null) race.trackCondition,
                      ].join('  ·  '),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    trailing: race.isCompleted
                        ? const Tag(text: 'result')
                        : const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => RaceDetailScreen(raceId: race.id),
                      ),
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}