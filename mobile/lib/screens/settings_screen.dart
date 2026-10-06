/// Settings: API server address, sign-in/out and cache controls.
library;

import 'package:flutter/material.dart';

import '../api.dart';
import '../scope.dart';
import '../widgets.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  String? _message;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _urlController.text = AppScope.of(context).api.baseUrl;
    });
  }

  @override
  void dispose() {
    _urlController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _saveUrl() async {
    await AppScope.of(context).setServerUrl(_urlController.text);
    if (!mounted) return;
    setState(() => _message = 'Server address saved.');
  }

  Future<void> _signIn() async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await AppScope.of(context).signIn(
        email: _emailController.text.trim(),
        password: _passwordController.text,
      );
      if (!mounted) return;
      setState(() {
        _message = 'Signed in.';
        _passwordController.clear();
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _message = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _signOut() async {
    await AppScope.of(context).signOut();
    if (!mounted) return;
    setState(() => _message = 'Signed out.');
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
        children: [
          SectionCard(
            title: 'Server',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _urlController,
                  decoration: const InputDecoration(
                    labelText: 'API base URL',
                    helperText: 'Android emulator: http://10.0.2.2:8000  ·  '
                        'phone on your Wi-Fi: http://<pc-ip>:8000',
                    helperMaxLines: 3,
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                ),
                const SizedBox(height: 8),
                FilledButton.tonal(onPressed: _saveUrl, child: const Text('Save')),
                const SizedBox(height: 6),
                Text(
                  'Current: ${state.api.baseUrl}',
                  style: theme.textTheme.labelSmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
          SectionCard(
            title: state.signedIn ? 'Account (signed in)' : 'Account',
            child: state.signedIn
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(state.email ?? 'signed in'),
                      const SizedBox(height: 8),
                      OutlinedButton(
                        onPressed: _signOut,
                        child: const Text('Sign out'),
                      ),
                    ],
                  )
                : Column(
                    children: [
                      TextField(
                        controller: _emailController,
                        decoration: const InputDecoration(
                          labelText: 'Email',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _passwordController,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'Password',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                      ),
                      const SizedBox(height: 10),
                      FilledButton(
                        onPressed: _busy ? null : _signIn,
                        child: Text(_busy ? 'Signing in…' : 'Sign in'),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Signing in unlocks followed horses and alerts.',
                        style: theme.textTheme.labelSmall
                            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ],
                  ),
          ),
          SectionCard(
            title: 'Cache',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Payloads are cached on the device so the app opens instantly and '
                  'keeps working when the network drops. Pull-to-refresh on any '
                  'screen forces a fresh fetch.',
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: () {
                    state.api.logout();
                    setState(() => _message = 'Local cache cleared.');
                  },
                  child: const Text('Clear cached data'),
                ),
              ],
            ),
          ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_message!, style: theme.textTheme.bodySmall),
            ),
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(
              'FormEdge mobile · predictions are pre-computed by the background '
              'pipeline. Not betting advice.',
              style: theme.textTheme.labelSmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
        ],
      ),
    );
  }
}