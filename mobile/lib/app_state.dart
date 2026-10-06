/// Shared app state: the API client, the saved server URL and the signed-in user.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

/// Default API base.
///
/// The Android emulator reaches the host machine at 10.0.2.2, not localhost —
/// see docs/mobile-guide.md for the physical-device case.
const String kDefaultApiBase = 'http://10.0.2.2:8000';

class AppState extends ChangeNotifier {
  AppState({FormEdgeApi? api, SharedPreferences? prefs})
      : api = api ?? FormEdgeApi(baseUrl: kDefaultApiBase),
        _prefs = prefs;

  final FormEdgeApi api;
  SharedPreferences? _prefs;
  bool _ready = false;
  String? _email;

  bool get ready => _ready;
  bool get signedIn => api.token != null;
  String? get email => _email;

  /// Restore the saved server URL and JWT, then allow the UI to load.
  Future<void> bootstrap() async {
    try {
      _prefs ??= await SharedPreferences.getInstance();
      await api.restore(_prefs!);
      _email = _prefs!.getString('email');
    } catch (_) {
      // Storage may be unavailable (e.g. restricted web sandbox): carry on with
      // in-memory defaults rather than blocking the app.
    }
    _ready = true;
    notifyListeners();
  }

  Future<void> setServerUrl(String url) async {
    final trimmed = url.trim();
    if (trimmed.isEmpty) return;
    api.baseUrl = trimmed;
    await _prefs?.setString('api_base_url', trimmed);
    notifyListeners();
  }

  Future<void> signIn({required String email, required String password}) async {
    await api.login(email: email, password: password);
    _email = email.trim();
    await _prefs?.setString('email', _email!);
    await api.persist(_prefs ?? await SharedPreferences.getInstance());
    notifyListeners();
  }

  Future<void> signOut() async {
    api.logout();
    _email = null;
    await _prefs?.remove('jwt');
    notifyListeners();
  }
}