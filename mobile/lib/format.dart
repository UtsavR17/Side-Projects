/// Small formatting helpers (kept dependency-free on purpose).
library;

const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/// `2026-09-19T12:30:00` -> `Sat 19 Sep 2026`.
String fmtDate(String? iso) {
  final parsed = DateTime.tryParse(iso ?? '');
  if (parsed == null) return iso ?? '-';
  return '${_weekdays[parsed.weekday - 1]} ${parsed.day} ${_months[parsed.month - 1]}'
      ' ${parsed.year}';
}

/// `2026-09-19T12:30:00` -> `12:30`.
String fmtTime(String? iso) {
  final parsed = DateTime.tryParse(iso ?? '');
  if (parsed == null) return '';
  final hh = parsed.hour.toString().padLeft(2, '0');
  final mm = parsed.minute.toString().padLeft(2, '0');
  return '$hh:$mm';
}

/// The race time label if the importer captured one, else the timestamp's time.
String raceTime(String? label, String? iso) {
  if (label != null && label.trim().isNotEmpty) return label.trim();
  return fmtTime(iso);
}

/// 0.2841 -> `28.4%`.
String pct(double? value, {int digits = 1}) {
  if (value == null) return '-';
  return '${(value * 100).toStringAsFixed(digits)}%';
}

/// Trim trailing `.0` from weights and odds.
String num1(double? value) {
  if (value == null) return '-';
  final text = value.toStringAsFixed(1);
  return text.endsWith('.0') ? text.substring(0, text.length - 2) : text;
}

/// Whole seconds as `1:24.88` (race times come back in seconds).
String raceTimeOfDay(double? seconds) {
  if (seconds == null) return '-';
  final minutes = seconds ~/ 60;
  final rest = seconds - minutes * 60;
  return '$minutes:${rest.toStringAsFixed(2).padLeft(5, '0')}';
}

/// `2026-09-19T12:30:00` -> `in 3 days` / `2 days ago`.
String relativeToNow(String? iso) {
  final parsed = DateTime.tryParse(iso ?? '');
  if (parsed == null) return '';
  final days = parsed.difference(DateTime.now()).inDays;
  if (days == 0) return 'today';
  if (days == 1) return 'tomorrow';
  if (days == -1) return 'yesterday';
  return days > 0 ? 'in $days days' : '${-days} days ago';
}