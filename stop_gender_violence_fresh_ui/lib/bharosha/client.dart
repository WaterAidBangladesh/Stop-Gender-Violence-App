/// Talks to the Bharosha service. Only ever for explanatory answers.
///
/// Nothing on the life-safety path comes through here: emergencies, refusals and
/// the referral numbers are matched and rendered on the device, so they work with
/// the radio off. This client is for the questions that can wait — what
/// safeguarding means, what the forms of violence are — and when it fails, the
/// caller falls back to the same local referral text.
///
/// THE SESSION ID IS NOT AN IDENTITY. It is 32 random hex characters generated
/// per conversation, never the Firebase uid and nothing derived from it. The
/// server uses it as an opaque key for ephemeral history that expires, so two
/// conversations from the same person cannot be linked to each other or to her.

import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;

/// Where the service lives. Override at build time:
///   flutter run --dart-define=BHAROSHA_URL=https://your-service.onrender.com
const String bharoshaBaseUrl = String.fromEnvironment(
  'BHAROSHA_URL',
  defaultValue: '',
);

/// A fresh, unlinkable conversation key.
String newSessionId() {
  final random = Random.secure();
  return List.generate(16, (_) => random.nextInt(256))
      .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
      .join();
}

class BharoshaReply {
  const BharoshaReply({required this.text, required this.kind});

  final String text;

  /// `answer`, `no_context`, `emergency`, `refusal`, `rate_limited`, or
  /// `unreachable` when the request never completed.
  final String kind;

  bool get isAnswer => kind == 'answer';
}

class BharoshaClient {
  BharoshaClient({http.Client? httpClient, this.timeout = const Duration(seconds: 30)})
      : _http = httpClient ?? http.Client();

  final http.Client _http;
  final Duration timeout;

  bool get isConfigured => bharoshaBaseUrl.isNotEmpty;

  /// Ask a question. Returns `kind: 'unreachable'` rather than throwing.
  ///
  /// Deliberately never throws: every caller would have to catch it to show the
  /// referral text anyway, and an uncaught exception on this screen would leave
  /// someone staring at a spinner.
  Future<BharoshaReply> ask({
    required String sessionId,
    required String query,
  }) async {
    if (!isConfigured) {
      return const BharoshaReply(text: '', kind: 'unreachable');
    }
    try {
      final response = await _http
          .post(
            Uri.parse('$bharoshaBaseUrl/chat'),
            headers: const {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode({'session_id': sessionId, 'query': query}),
          )
          .timeout(timeout);

      if (response.statusCode != 200) {
        return const BharoshaReply(text: '', kind: 'unreachable');
      }
      // utf8.decode, not response.body: the body is Bangla and response.body
      // guesses latin-1 when the server omits a charset, which mangles it.
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final text = (data['response'] as String?) ?? '';
      if (text.trim().isEmpty) {
        return const BharoshaReply(text: '', kind: 'unreachable');
      }
      return BharoshaReply(
        text: text,
        kind: (data['kind'] as String?) ?? 'answer',
      );
    } catch (_) {
      // Offline, DNS failure, timeout, a sleeping free-tier instance: all the
      // same outcome to the user, and the caller shows the local referral.
      return const BharoshaReply(text: '', kind: 'unreachable');
    }
  }

  /// Ask the server to forget this conversation. Best effort, never awaited by UI.
  Future<void> forget(String sessionId) async {
    if (!isConfigured) return;
    try {
      await _http
          .post(
            Uri.parse('$bharoshaBaseUrl/forget'),
            headers: const {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode({'session_id': sessionId}),
          )
          .timeout(const Duration(seconds: 5));
    } catch (_) {
      // The server expires sessions on its own; this only makes it immediate.
    }
  }

  void close() => _http.close();
}
