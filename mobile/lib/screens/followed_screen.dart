/// Followed horses (requires sign-in).
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../scope.dart';
import '../widgets.dart';
import 'horse_detail_screen.dart';

class FollowedScreen extends StatefulWidget {
  const FollowedScreen({super.key});

  @override
  State<FollowedScreen> createState() => _FollowedScreenState();
}

class _FollowedScreenState extends State<FollowedScreen> {
  List<NameId> _horses = const [];
  List<NameId> _results = const [];
  bool _loading = false;
  String? _error;
  String _search = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final state = AppScope.of(context);
    if (!state.signedIn) {
      setState(() {
        _horses = const [];
        _loading = false;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final horses = await state.api.followedHorses();
      if (!mounted) return;
      setState(() {
        _horses = horses;
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

  Future<void> _runSearch(String value) async {
    setState(() => _search = value);
    if (value.trim().length < 2) {
      setState(() => _results = const []);
      return;
    }
    try {
      final results = await AppScope.of(context).api.searchHorses(value);
      if (!mounted) return;
      setState(() => _results = results);
    } on ApiException {
      // A failed search is non-fatal: keep whatever is on screen.
    }
  }

  Future<void> _toggleFollow(int horseId, bool follow) async {
    final state = AppScope.of(context);
    try {
      if (follow) {
        await state.api.followHorse(horseId);
      } else {
        await state.api.unfollowHorse(horseId);
      }
      await _load();
      if (_search.trim().length >= 2) await _runSearch(_search);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final signedIn = AppScope.of(context).signedIn;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Followed horses'),
        actions: [
          if (signedIn)
            IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: !signedIn
          ? const PlaceholderMessage(
              icon: Icons.lock_outline,
              title: 'Sign in to follow horses',
              message: 'Add your account in Settings — followed horses drive the '
                  'alerts you receive.',
            )
          : _loading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
                  children: [
                    TextField(
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search),
                        labelText: 'Search horses to follow',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onChanged: _runSearch,
                    ),
                    if (_results.isNotEmpty)
                      SectionCard(
                        title: 'Search results',
                        child: Column(
                          children: [
                            for (final horse in _results)
                              ListTile(
                                dense: true,
                                title: Text(horse.name),
                                trailing: IconButton(
                                  tooltip: 'Follow',
                                  icon: const Icon(Icons.add_circle_outline),
                                  onPressed: () => _toggleFollow(horse.id, true),
                                ),
                              ),
                          ],
                        ),
                      ),
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Text(
                          _error!,
                          style: theme.textTheme.bodySmall
                              ?.copyWith(color: theme.colorScheme.error),
                        ),
                      ),
                    if (_horses.isEmpty)
                      const SectionCard(
                        title: 'Your horses',
                        child: Text(
                          'Nothing followed yet — search above and tap + to follow.',
                        ),
                      )
                    else
                      SectionCard(
                        title: 'Your horses (${_horses.length})',
                        child: Column(
                          children: [
                            for (final horse in _horses)
                              ListTile(
                                dense: true,
                                leading: const Icon(Icons.star, size: 18),
                                title: Text(horse.name),
                                trailing: IconButton(
                                  tooltip: 'Unfollow',
                                  icon: const Icon(Icons.remove_circle_outline),
                                  onPressed: () => _toggleFollow(horse.id, false),
                                ),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute<void>(
                                    builder: (_) =>
                                        HorseDetailScreen(horseId: horse.id),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                  ],
                ),
    );
  }
}