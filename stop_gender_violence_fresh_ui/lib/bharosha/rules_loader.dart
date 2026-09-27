/// Loads the bundled safety rules and referral text once, at first use.
///
/// The JSON lives in the app bundle, so this is a local read with no network and
/// no permissions. It is cached because the chat screen may be opened and closed
/// repeatedly and re-parsing 28 KB each time would add latency to the one screen
/// that must feel instant.

import 'package:flutter/services.dart' show rootBundle;

import 'referrals.dart';
import 'safety.dart';

class BharoshaRules {
  BharoshaRules._(this.safety, this.referrals);

  final SafetyRules safety;
  final Referrals referrals;

  static BharoshaRules? _cached;
  static Future<BharoshaRules>? _loading;

  /// Load (or return the cached) rules.
  ///
  /// The in-flight future is cached as well, so two screens opening at once do
  /// not both parse the assets.
  static Future<BharoshaRules> load() {
    final cached = _cached;
    if (cached != null) return Future.value(cached);
    return _loading ??= _read();
  }

  static Future<BharoshaRules> _read() async {
    final rulesJson = await rootBundle.loadString('assets/bharosha/safety_rules.json');
    final referralJson = await rootBundle.loadString('assets/bharosha/referrals.json');
    final rules = BharoshaRules._(
      SafetyRules.fromJson(rulesJson),
      Referrals.fromJson(referralJson),
    );
    _cached = rules;
    return rules;
  }
}
