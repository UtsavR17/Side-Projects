/// In-app notifications (new predictions, results, followed-horse alerts).
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../models.dart';
import '../scope.dart';
import '../widgets.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  NotificationPage? _page;
  bool _loading = false;
  String? _error;
  bool _unreadOnly = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final state = AppScope.of(context);
    if (!state.signedIn) {
      setState(() {
        _page = null;
        _loading = false;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await state.api.notifications(unreadOnly: _unreadOnly);
      if (!mounted) return;
      setState(() {
        _page = page;
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

  Future<void> _markAll() async {
    try {
      await AppScope.of(context).api.markAllNotificationsRead();
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  Future<void> _markOne(AppNotification notification) async {
    try {
      await AppScope.of(context).api.markNotificationRead(notification.id);
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  IconData _iconFor(String category) {
    switch (category) {
      case 'fixtures':
        return Icons.event_available;
      case 'predictions_ready':
        return Icons.insights;
      case 'prediction_updated':
        return Icons.swap_vert;
      case 'result_posted':
        return Icons.emoji_events_outlined;
      case 'weekly_summary':
        return Icons.calendar_month;
      case 'followed_horse':
        return Icons.star_border;
      default:
        return Icons.notifications_none;
    }
  }

  @override
  Widget build(BuildContext context) {
    final signedIn = AppScope.of(context).signedIn;
    final page = _page;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(
          page == null
              ? 'Alerts'
              : 'Alerts${page.unreadCount > 0 ? ' (${page.unreadCount})' : ''}',
        ),
        actions: [
          if (signedIn) ...[
            IconButton(
              tooltip: _unreadOnly ? 'Show all' : 'Show unread only',
              icon: Icon(_unreadOnly ? Icons.filter_alt : Icons.filter_alt_outlined),
              onPressed: () {
                setState(() => _unreadOnly = !_unreadOnly);
                _load();
              },
            ),
            IconButton(
              tooltip: 'Mark all read',
              icon: const Icon(Icons.done_all),
              onPressed: _markAll,
            ),
          ],
        ],
      ),
      body: !signedIn
          ? const PlaceholderMessage(
              icon: Icons.lock_outline,
              title: 'Sign in to see alerts',
              message: 'Alerts are produced by the background pipeline and stored '
                  'per account.',
            )
          : _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? PlaceholderMessage(
                      icon: Icons.cloud_off,
                      title: 'Cannot load alerts',
                      message: _error,
                      onRetry: _load,
                    )
                  : page == null || page.notifications.isEmpty
                      ? const PlaceholderMessage(
                          icon: Icons.notifications_off_outlined,
                          title: 'No alerts yet',
                          message: 'New fixtures, fresh predictions and results '
                              'will appear here.',
                        )
                      : RefreshIndicator(
                          onRefresh: _load,
                          child: ListView(
                            padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
                            children: [
                              for (final notification in page.notifications)
                                Card(
                                  margin: const EdgeInsets.symmetric(vertical: 4),
                                  child: ListTile(
                                    leading: Icon(_iconFor(notification.category)),
                                    title: Text(
                                      notification.title,
                                      style: TextStyle(
                                        fontWeight: notification.isRead
                                            ? FontWeight.w400
                                            : FontWeight.w700,
                                      ),
                                    ),
                                    subtitle: notification.body == null
                                        ? null
                                        : Text(notification.body!),
                                    trailing: notification.isRead
                                        ? null
                                        : IconButton(
                                            tooltip: 'Mark read',
                                            icon: const Icon(Icons.check, size: 18),
                                            onPressed: () => _markOne(notification),
                                          ),
                                  ),
                                ),
                              Padding(
                                padding: const EdgeInsets.only(top: 8),
                                child: Text(
                                  'Push delivery (FCM) is wired on the backend; see '
                                  'docs/mobile-guide.md to enable it.',
                                  style: theme.textTheme.labelSmall?.copyWith(
                                    color: theme.colorScheme.onSurfaceVariant,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
    );
  }
}