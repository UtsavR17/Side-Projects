/// FormEdge mobile — horse racing predictions and analytics.
///
/// The app only ever reads pre-computed data from the FormEdge API (the pipeline
/// runs on a schedule server-side) and caches every payload locally, so screens
/// open instantly and keep working when the network drops.
library;

import 'package:flutter/material.dart';

import 'app_state.dart';
import 'scope.dart';
import 'screens/alerts_screen.dart';
import 'screens/followed_screen.dart';
import 'screens/picks_screen.dart';
import 'screens/races_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const FormEdgeApp());
}

class FormEdgeApp extends StatefulWidget {
  const FormEdgeApp({super.key, this.state});

  /// Injectable for tests.
  final AppState? state;

  @override
  State<FormEdgeApp> createState() => _FormEdgeAppState();
}

class _FormEdgeAppState extends State<FormEdgeApp> {
  late final AppState _state = widget.state ?? AppState();

  @override
  void initState() {
    super.initState();
    _state.bootstrap();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      state: _state,
      child: MaterialApp(
        title: 'FormEdge',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF4F8CFF),
            brightness: Brightness.dark,
          ),
        ),
        home: const HomeShell(),
      ),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _screens = <Widget>[
    RacesScreen(),
    PicksScreen(),
    FollowedScreen(),
    AlertsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    if (!state.ready) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.event_outlined),
            selectedIcon: Icon(Icons.event),
            label: 'Races',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            selectedIcon: Icon(Icons.insights),
            label: 'Picks',
          ),
          NavigationDestination(
            icon: Icon(Icons.star_border),
            selectedIcon: Icon(Icons.star),
            label: 'Followed',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_none),
            selectedIcon: Icon(Icons.notifications),
            label: 'Alerts',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}