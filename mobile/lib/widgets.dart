/// Reusable presentational widgets.
library;

import 'package:flutter/material.dart';

import 'format.dart';
import 'models.dart';

/// Horizontal probability bar (0..1) with the percentage beside it.
class ProbBar extends StatelessWidget {
  const ProbBar({
    super.key,
    required this.value,
    this.width = 84,
    this.showLabel = true,
    this.color,
  });

  final double value;
  final double width;
  final bool showLabel;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: width,
          height: 8,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: value.clamp(0.0, 1.0),
              backgroundColor: theme.colorScheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation<Color>(
                color ?? theme.colorScheme.primary,
              ),
            ),
          ),
        ),
        if (showLabel) ...[
          const SizedBox(width: 8),
          Text(pct(value), style: theme.textTheme.bodySmall),
        ],
      ],
    );
  }
}

/// Small labelled statistic tile.
class StatTile extends StatelessWidget {
  const StatTile({super.key, required this.label, required this.value, this.tint});

  final String label;
  final String value;
  final Color? tint;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              value,
              style: theme.textTheme.titleMedium
                  ?.copyWith(fontWeight: FontWeight.w800, color: tint),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              textAlign: TextAlign.center,
              style: theme.textTheme.labelSmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}

/// Coloured chip for a direction or status.
class Tag extends StatelessWidget {
  const Tag({super.key, required this.text, this.color});

  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final base = color ?? Theme.of(context).colorScheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: base.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: base.withValues(alpha: 0.5)),
      ),
      child: Text(
        text,
        style: Theme.of(context)
            .textTheme
            .labelSmall
            ?.copyWith(color: base, fontWeight: FontWeight.w700),
      ),
    );
  }
}

/// A card with a title, optional trailing widget and content.
class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.title,
    required this.child,
    this.trailing,
  });

  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context)
                        .textTheme
                        .titleSmall
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                ),
                if (trailing != null) ?trailing,
              ],
            ),
            const SizedBox(height: 8),
            child,
          ],
        ),
      ),
    );
  }
}

/// Standard empty / error state with an optional retry.
class PlaceholderMessage extends StatelessWidget {
  const PlaceholderMessage({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.onRetry,
    this.retryLabel = 'Retry',
  });

  final IconData icon;
  final String title;
  final String? message;
  final VoidCallback? onRetry;
  final String retryLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: 12),
            Text(title, textAlign: TextAlign.center, style: theme.textTheme.titleSmall),
            if (message != null) ...[
              const SizedBox(height: 6),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
            if (onRetry != null) ...[
              const SizedBox(height: 14),
              FilledButton.tonal(onPressed: onRetry, child: Text(retryLabel)),
            ],
          ],
        ),
      ),
    );
  }
}

/// One runner row (race card + race detail).
class RunnerRow extends StatelessWidget {
  const RunnerRow({
    super.key,
    required this.entry,
    this.onTap,
    this.showOfficial = true,
  });

  final Entry entry;
  final VoidCallback? onTap;
  final bool showOfficial;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final prediction = entry.ensemble;
    final odds = entry.displayOdds;
    final bodyWeight = entry.bodyWeightKg == null
        ? null
        : 'Hwt ${num1(entry.bodyWeightKg)}'
            '${entry.bodyWeightDelta != null ? ' (${entry.bodyWeightDelta! > 0 ? '+' : ''}${num1(entry.bodyWeightDelta)})' : ''}';

    final meta = [
      if (entry.jockeyName != null) 'J: ${entry.jockeyName}',
      if (entry.trainerName != null) 'T: ${entry.trainerName}',
      if (showOfficial && entry.rating != null) 'Rtg ${entry.rating}',
      if (showOfficial && entry.gear != null) 'Gear ${entry.gear}',
      if (showOfficial && bodyWeight != null) bodyWeight,
    ].join('  ·  ');

    return ListTile(
      dense: true,
      onTap: onTap,
      leading: CircleAvatar(
        radius: 15,
        child: Text(
          '${entry.saddleNo ?? entry.barrier ?? '-'}',
          style: theme.textTheme.labelSmall,
        ),
      ),
      title: Text(
        entry.horseName,
        style: TextStyle(
          fontWeight: FontWeight.w600,
          decoration: entry.scratched ? TextDecoration.lineThrough : null,
        ),
      ),
      subtitle: meta.isEmpty
          ? null
          : Text(
              meta,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall,
            ),
      trailing: SizedBox(
        width: 108,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (prediction != null)
              ProbBar(value: prediction.winProb, width: 52)
            else
              Text('no pick', style: theme.textTheme.labelSmall),
            Text(
              odds != null ? '@${num1(odds)}' : '',
              style: theme.textTheme.labelSmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}