/// Bharosha's safety layer, on the device.
///
/// WHY THIS RUNS HERE AND NOT ONLY ON THE SERVER. Emergency detection is plain
/// pattern matching and the referral responses are fixed strings, so neither
/// needs a network. Connectivity in rural Bangladesh is unreliable and a free
/// server instance sleeps when idle — a woman in danger should not need either
/// to be shown 999 and 109. On this path there is no HTTP request, no model, and
/// no waiting: she types, and the numbers are on screen.
///
/// The server keeps the same layer as defence in depth, for app versions that
/// still post raw questions to it.
///
/// THE RULES ARE NOT WRITTEN HERE. They are generated from the Python source by
/// bharosha_service/tools/export_shared.py into assets/bharosha/safety_rules.json,
/// because two hand-maintained copies of life-safety patterns in two languages
/// would drift, and the drift would be silent. A Python test fails while the
/// generated files are stale, and the Dart test in test/bharosha/ runs the same
/// shared case corpus as pytest.
///
/// ONE KNOWN PARITY GAP, deliberately accepted: Python normalises to Unicode NFC
/// before matching and Dart has no NFC in its core library. Both sides strip
/// zero-width joiners and lowercase, which covers what users actually type; a
/// decomposed Bangla sequence could in principle match on the server and not
/// here. If that ever matters, add a normalisation package rather than
/// hand-rolling it.
// (No `library;` directive: pubspec pins the language version to 2.18, which
// predates unnamed libraries.)

import 'dart:convert';

/// What the safety layer decided about one message.
class SafetyDecision {
  const SafetyDecision({
    required this.kind,
    required this.category,
    required this.language,
    required this.matched,
  });

  /// `emergency`, `refuse`, or `proceed`.
  final String kind;

  /// The winning category, or null when proceeding.
  final String? category;

  /// `bn` or `en` — which language to answer in.
  final String language;

  /// Every category that fired, for debugging. Never logged or transmitted.
  final List<String> matched;

  /// True when the model and the network must not be involved at all.
  bool get stopsTurn => kind == 'emergency' || kind == 'refuse';
}

class _NearRule {
  _NearRule({
    required this.category,
    required this.first,
    required this.second,
    required this.window,
  });

  final String category;
  final List<String> first;
  final List<String> second;
  final int window;
}

/// The compiled rule set. Load once at startup and keep it.
class SafetyRules {
  SafetyRules._({
    required this.priority,
    required this.emergencyCategories,
    required this.refusalCategories,
    required Map<String, List<RegExp>> patterns,
    required List<_NearRule> nearRules,
    required List<String> invisibleCharacters,
  })  : _patterns = patterns,
        _nearRules = nearRules,
        _invisible = RegExp('[${invisibleCharacters.join()}]');

  final List<String> priority;
  final List<String> emergencyCategories;
  final List<String> refusalCategories;
  final Map<String, List<RegExp>> _patterns;
  final List<_NearRule> _nearRules;
  final RegExp _invisible;

  static final RegExp _bengali = RegExp(r'[ঀ-৿]');
  static final RegExp _whitespace = RegExp(r'\s+');

  /// Build from the generated JSON.
  ///
  /// Takes the string rather than reading the asset itself so the test can feed
  /// it from disk and the app from `rootBundle` — the parsing being tested is
  /// then exactly the parsing that ships.
  factory SafetyRules.fromJson(String source) {
    final data = jsonDecode(source) as Map<String, dynamic>;

    final patterns = <String, List<RegExp>>{};
    (data['patterns'] as Map<String, dynamic>).forEach((category, list) {
      patterns[category] = [
        for (final pattern in (list as List).cast<String>()) RegExp(pattern),
      ];
    });

    return SafetyRules._(
      priority: (data['priority'] as List).cast<String>(),
      emergencyCategories:
          (data['emergency_categories'] as List).cast<String>(),
      refusalCategories: (data['refusal_categories'] as List).cast<String>(),
      patterns: patterns,
      nearRules: [
        for (final rule in (data['near_rules'] as List))
          _NearRule(
            category: rule['category'] as String,
            first: (rule['first'] as List).cast<String>(),
            second: (rule['second'] as List).cast<String>(),
            window: rule['window'] as int,
          ),
      ],
      invisibleCharacters:
          (data['invisible_characters'] as List).cast<String>(),
    );
  }

  /// Fold a message to the form the patterns are written against.
  String normalise(String text) {
    final stripped = text.replaceAll(_invisible, '').toLowerCase();
    return stripped.replaceAll(_whitespace, ' ').trim();
  }

  /// `bn` when the message contains any Bangla, else `en`.
  ///
  /// Script presence, not proportion: one Bangla clause in a mixed sentence is
  /// answered in Bangla. Romanised Bangla ("amake marche") is answered in
  /// English, which is what someone typing Latin characters can read.
  String detectLanguage(String text) => _bengali.hasMatch(text) ? 'bn' : 'en';

  /// Prefix match for Latin terms, substring for Bangla.
  ///
  /// "hit" as a prefix matches "hitting" but not "white". Bangla inflects by
  /// suffixing, so "মেয়ে" has to match inside "মেয়েকে". Identical to the Python
  /// side; changing one without the other breaks the shared cases.
  static bool _matchesTerm(String token, String term) {
    final isAscii = term.codeUnits.every((unit) => unit < 128);
    return isAscii ? token.startsWith(term) : token.contains(term);
  }

  bool _nearMatch(List<String> tokens, _NearRule rule) {
    final firsts = <int>[];
    final seconds = <int>[];
    for (var i = 0; i < tokens.length; i++) {
      if (rule.first.any((term) => _matchesTerm(tokens[i], term))) firsts.add(i);
      if (rule.second.any((term) => _matchesTerm(tokens[i], term))) {
        seconds.add(i);
      }
    }
    for (final i in firsts) {
      for (final j in seconds) {
        if (i != j && (i - j).abs() <= rule.window) return true;
      }
    }
    return false;
  }

  bool _fires(String category, String text, List<String> tokens) {
    for (final pattern in _patterns[category] ?? const <RegExp>[]) {
      if (pattern.hasMatch(text)) return true;
    }
    for (final rule in _nearRules) {
      if (rule.category == category && _nearMatch(tokens, rule)) return true;
    }
    return false;
  }

  /// Classify one message. Pure, synchronous, offline, no model.
  ///
  /// The first category in `priority` that fires wins, so the outcome never
  /// depends on map ordering. Emergencies are checked before refusals: "he will
  /// kill me if I leave" is an emergency, not a question about leaving.
  SafetyDecision classify(String message) {
    final language = detectLanguage(message);
    final text = normalise(message);
    final tokens = text.isEmpty ? <String>[] : text.split(' ');

    final matched = <String>[];
    for (final category in priority) {
      if (_fires(category, text, tokens)) matched.add(category);
    }

    for (final category in priority) {
      if (!matched.contains(category)) continue;
      return SafetyDecision(
        kind: emergencyCategories.contains(category) ? 'emergency' : 'refuse',
        category: category,
        language: language,
        matched: matched,
      );
    }

    return SafetyDecision(
      kind: 'proceed',
      category: null,
      language: language,
      matched: const [],
    );
  }
}
