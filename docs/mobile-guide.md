# Mobile Guide — FormEdge Flutter app

`mobile/` is a Flutter client for the FormEdge API (Prompt E). It is **read-only**:
the backend pipeline does the scraping, feature engineering and model runs, and
the app just displays pre-computed results — with local caching so screens open
instantly and keep working when the network drops.

## Screens

| Tab | What it shows |
|---|---|
| **Races** | Upcoming meetings grouped by day; a toggle switches to recent results. Tap a race for the full card. |
| **Picks** | Today's meeting with the model's top pick and top-4 per race, plus past results vs predictions (HIT/miss) and the model leaderboard. |
| **Followed** | Search horses and follow/unfollow (needs sign-in) — the same follows that drive backend alerts. |
| **Alerts** | In-app notifications from the pipeline (fixtures, predictions ready, odds moves, results, weekly digest, followed-horse). Mark one/all read. |
| **Settings** | API base URL, sign-in/out, clear cache. |

Race detail shows the ensemble probabilities, the stored explanation factors,
finish positions, and the official MTC extras when imported (SP, rating, gear,
horse body weight + change, sectionals and the tote dividend ladder). Horse
profiles show career stats, distance/going splits, form score, and per-run
official fields.

## Running it

```bash
cd mobile
flutter pub get
flutter run                # pick a device: emulator, phone, or Chrome
```

### Point it at your backend

The default base URL is `http://10.0.2.2:8000` — the Android emulator's alias for
your PC's localhost. For a physical phone, use your PC's LAN address and start the
API on all interfaces:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then set `http://<your-pc-ip>:8000` in **Settings → Server → API base URL**
(Windows: `ipconfig` → IPv4 address). Same Wi-Fi required, and allow the port
through the firewall.

### Checks (also run in CI)

```bash
flutter analyze
flutter test
```

## Performance design (matches the master plan)

- **Never waits on a scrape or a model run.** The API serves cached, pre-computed
  data; the app never triggers a pipeline job.
- **Local cache per request path** with a 10-minute freshness window
  (`FormEdgeApi._cache`): a fresh copy is used when available, and the last good
  payload is served when the network fails instead of showing an error.
- **Pull-to-refresh** on every list forces a bypass of the cache.
- Small screens issue few calls: the Picks tab loads only the next meeting's
  races (max 6) plus history and the leaderboard.

## Push notifications (FCM)

In-app alerts work out of the box (they are rows in `notifications`, fetched via
`GET /api/notifications`). Push delivery is optional and needs Firebase config:

1. Create a Firebase project, add an Android app with package `com.formedge.formedge_mobile`
   (and an iOS app if needed), then download `google-services.json` into
   `mobile/android/app/` (`GoogleService-Info.plist` into `mobile/ios/Runner/`).
2. Add the packages: `flutter pub add firebase_core firebase_messaging`.
3. After login, obtain the device token and register it:

   ```dart
   await state.api.registerDeviceToken(fcmToken, 'android');
   ```

   That hits `POST /api/me/device-tokens` (the `device_tokens` table already
   exists). The backend's pipeline then pushes via the FCM HTTP v1 hook
   (`app/services/fcm.py`) when `FCM_ENABLED=true` and credentials are set.

Without Firebase the app still shows everything — only OS-level push is missing.

## Tests

`test/models_test.dart` covers the JSON contract (including the official MTC
fields and a sparse "older cache" payload), the ensemble ordering/top-pick logic,
and the formatting helpers. No network or platform channels are required, so it
runs anywhere CI runs.

## Not done yet

- FCM wiring (above) and a device-token UI toggle.
- Server-Sent Events streaming in the app (the API exposes `/api/events`); today
  the app refreshes on pull-to-refresh and on tab switches.
- iOS build needs a Mac with Xcode — the project scaffold is committed, but only
  Android/web have been compiled here.