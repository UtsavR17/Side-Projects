/// FormEdge API client: cache-first reads, JWT auth, typed models.
///
/// Design notes
/// ------------
/// * The backend serves PRE-COMPUTED data (the pipeline runs on a schedule), so
///   the app never waits on a scrape or a model run — and ISR/Redis on the
///   server side makes these calls cheap.
/// * Every GET is cached locally (last-good payload + timestamp) so re-opening
///   the app shows content instantly and works offline-ish. A failed refresh
///   falls back to the cache instead of an error screen.
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => statusCode == null ? message : '($statusCode) $message';
}

/// Cached value + when it was fetched.
class CacheEntry {
  CacheEntry(this.value, this.fetchedAt);

  final Object value;
  final DateTime fetchedAt;

  Duration get age => DateTime.now().difference(fetchedAt);
}

class FormEdgeApi {
  FormEdgeApi({required this.baseUrl, this.client});

  /// Base URL of the FormEdge API, e.g. http://10.0.2.2:8000 for Android emulator.
  String baseUrl;
  final http.Client? client;

  static const Duration _timeout = Duration(seconds: 15);
  static const Duration cacheTtl = Duration(minutes: 10);

  final Map<String, CacheEntry> _cache = {};

  /// Token used for authenticated endpoints (follow/unfollow, notifications).
  String? token;

  http.Client get _http => client ?? http.Client();

  /// Save the API base URL and JWT so a restart keeps the session.
  Future<void> persist(SharedPreferences prefs) async {
    await prefs.setString('api_base_url', baseUrl);
    if (token != null) {
      await prefs.setString('jwt', token!);
    } else {
      await prefs.remove('jwt');
    }
  }

  Future<void> restore(SharedPreferences prefs) async {
    final stored = prefs.getString('api_base_url');
    if (stored != null && stored.trim().isNotEmpty) baseUrl = stored.trim();
    token = prefs.getString('jwt');
  }

  // ---------------------------------------------------------------- caching --
  CacheEntry? cached(String path) => _cache[path];

  /// Last-good value for a path (ignores freshness) — powers offline display.
  Object? cachedValue(String path) => _cache[path]?.value;

  void _store(String path, Object value) =>
      _cache[path] = CacheEntry(value, DateTime.now());

  Uri _uri(String path, [Map<String, String>? query]) {
    final normalised = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return Uri.parse('$normalised$path').replace(queryParameters: query);
  }

  Map<String, String> _headers({bool json = false}) => {
        if (json) 'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  /// GET with cache fallback. `T` is decoded by [decode].
  Future<T> _get<T>(
    String path,
    T Function(Object json) decode, {
    Map<String, String>? query,
    Duration? ttl,
    bool forceRefresh = false,
  }) async {
    final key = Uri(path: path, queryParameters: query).toString();
    final entry = _cache[key];
    final maxAge = ttl ?? cacheTtl;

    if (!forceRefresh && entry != null && entry.age < maxAge) {
      return decode(entry.value);
    }
    try {
      final response = await _http
          .get(_uri(path, query), headers: _headers())
          .timeout(_timeout);
      if (response.statusCode == 404) {
        throw ApiException('Not found', statusCode: 404);
      }
      if (response.statusCode >= 400) {
        throw ApiException('Request failed', statusCode: response.statusCode);
      }
      final decoded = jsonDecode(response.body) as Object;
      _store(key, decoded);
      return decode(decoded);
    } on ApiException {
      rethrow;
    } catch (error) {
      // Network problem: serve the last good copy if we have one.
      if (entry != null) return decode(entry.value);
      throw ApiException('Cannot reach $baseUrl ($error)');
    }
  }

  Future<T> _post<T>(
    String path,
    Object? body,
    T Function(Object json) decode, {
    bool forceRefresh = false,
  }) async {
    try {
      final response = await _http
          .post(
            _uri(path),
            headers: _headers(json: true),
            body: body == null ? null : jsonEncode(body),
          )
          .timeout(_timeout);
      if (response.statusCode >= 400) {
        throw ApiException('Request failed', statusCode: response.statusCode);
      }
      final decoded = response.body.isEmpty
          ? <String, Object?>{}
          : jsonDecode(response.body) as Object;
      if (forceRefresh) _cache.clear();
      return decode(decoded);
    } on ApiException {
      rethrow;
    } catch (error) {
      throw ApiException('Cannot reach $baseUrl ($error)');
    }
  }
// --------------------------------------------------------------- endpoints --

  Future<List<RaceSummary>> upcomingRaces({bool forceRefresh = false}) => _get(
        '/api/races',
        (json) => _listOf(json, 'races', RaceSummary.fromJson),
        forceRefresh: forceRefresh,
      );

  Future<List<RaceSummary>> recentRaces({bool forceRefresh = false}) => _get(
        '/api/races',
        (json) => _listOf(json, 'races', RaceSummary.fromJson),
        query: {'upcoming': 'false', 'limit': '40'},
        forceRefresh: forceRefresh,
      );

  Future<RaceDetail> raceDetail(int raceId) => _get(
        '/api/races/$raceId',
        (json) => RaceDetail.fromJson(json as Map<String, dynamic>),
      );

  Future<HorseProfile> horseProfile(int horseId) => _get(
        '/api/horses/$horseId',
        (json) => HorseProfile.fromJson(json as Map<String, dynamic>),
      );

  Future<List<NameId>> searchHorses(String search) => _get(
        '/api/horses',
        (json) => _listOf(json, 'horses', NameId.fromJson),
        query: {
          'limit': '50',
          if (search.trim().isNotEmpty) 'search': search.trim(),
        },
        ttl: const Duration(minutes: 30),
      );

  Future<List<NameId>> followedHorses() => _get(
        '/api/me/followed-horses',
        (json) => _listOf(json, 'horses', NameId.fromJson),
        forceRefresh: true,
      );

  Future<PredictionHistory> predictionHistory({int limit = 30}) => _get(
        '/api/predictions/history',
        (json) => PredictionHistory.fromJson(json as Map<String, dynamic>),
        query: {'limit': '$limit'},
      );

  Future<Leaderboard> leaderboard() => _get(
        '/api/leaderboard',
        (json) => Leaderboard.fromJson(json as Map<String, dynamic>),
      );

  Future<NotificationPage> notifications({bool unreadOnly = false}) => _get(
        '/api/notifications',
        (json) => NotificationPage.fromJson(json as Map<String, dynamic>),
        query: {'limit': '50', if (unreadOnly) 'unread_only': 'true'},
        forceRefresh: true,
      );

  Future<void> markNotificationRead(int id) =>
      _post<void>('/api/notifications/$id/read', null, _ignore, forceRefresh: true);

  Future<void> markAllNotificationsRead() =>
      _post<void>('/api/notifications/read-all', null, _ignore, forceRefresh: true);

  Future<bool> followHorse(int horseId) => _post(
        '/api/horses/$horseId/follow',
        null,
        (json) => (json as Map<String, dynamic>)['following'] == true,
        forceRefresh: true,
      );

  Future<bool> unfollowHorse(int horseId) async {
    try {
      final response = await _http.delete(
        _uri('/api/horses/$horseId/follow'),
        headers: _headers(),
      );
      if (response.statusCode >= 400) {
        throw ApiException('Unfollow failed', statusCode: response.statusCode);
      }
      _cache.clear();
      return false;
    } on ApiException {
      rethrow;
    } catch (error) {
      throw ApiException('Cannot reach $baseUrl ($error)');
    }
  }

  /// Sign in and keep the JWT for authenticated calls.
  Future<void> login({required String email, required String password}) async {
    final result = await _post(
      '/api/auth/login',
      {'email': email, 'password': password},
      (json) => (json as Map<String, dynamic>)['access_token'] as String?,
    );
    if (result == null || result.isEmpty) {
      throw ApiException('Login failed - no token returned');
    }
    token = result;
  }

  /// Register a mobile push token with the backend (`device_tokens` table).
  /// See docs/mobile-guide.md for wiring Firebase Cloud Messaging.
  Future<void> registerDeviceToken(String token, String platform) => _post<void>(
        '/api/me/device-tokens',
        {'token': token, 'platform': platform},
        _ignore,
      );

  void logout() {
    token = null;
    _cache.clear();
  }
}

/// Decoder for endpoints whose response body we don't need.
void _ignore(Object _) {}

List<T> _listOf<T>(
  Object json,
  String key,
  T Function(Map<String, dynamic>) build,
) {
  final map = json as Map<String, dynamic>;
  final items = map[key] as List<dynamic>? ?? const <dynamic>[];
  return items
      .whereType<Map<String, dynamic>>()
      .map(build)
      .toList(growable: false);
}