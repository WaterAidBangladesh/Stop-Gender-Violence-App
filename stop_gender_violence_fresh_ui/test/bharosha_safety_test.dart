/// Runs the SHARED case corpus against the Dart safety layer.
///
/// The cases in assets/bharosha/safety_cases.json are the same ones pytest runs
/// on the server, exported from the Python source. That is what makes "ported
/// with the same coverage" a checkable claim rather than an assertion: if the two
/// implementations ever disagree about a message, one of these tests fails.
///
/// The files are read from disk rather than through rootBundle so the suite needs
/// no Flutter binding and stays fast.
///
///     flutter test test/bharosha_safety_test.dart

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:stop_gender_violence_ui/bharosha/referrals.dart';
import 'package:stop_gender_violence_ui/bharosha/safety.dart';

void main() {
  final rules = SafetyRules.fromJson(
    File('assets/bharosha/safety_rules.json').readAsStringSync(),
  );
  final referrals = Referrals.fromJson(
    File('assets/bharosha/referrals.json').readAsStringSync(),
  );
  final cases = (jsonDecode(
    File('assets/bharosha/safety_cases.json').readAsStringSync(),
  )['cases'] as List)
      .cast<Map<String, dynamic>>();

  group('shared case corpus', () {
    test('has cases in both languages and all three outcomes', () {
      expect(cases.length, greaterThan(40));
      expect(cases.where((c) => c['language'] == 'bn'), isNotEmpty);
      expect(cases.where((c) => c['language'] == 'en'), isNotEmpty);
      for (final kind in ['emergency', 'refuse', 'proceed']) {
        expect(cases.where((c) => c['kind'] == kind), isNotEmpty,
            reason: 'no $kind cases in the shared corpus');
      }
    });

    for (final testCase in cases) {
      final message = testCase['message'] as String;
      final expectedKind = testCase['kind'] as String;
      final expectedCategory = testCase['category'] as String?;
      final expectedLanguage = testCase['language'] as String;

      test('[$expectedKind/${expectedCategory ?? '-'}] $message', () {
        final decision = rules.classify(message);
        expect(decision.kind, expectedKind,
            reason: 'Dart and Python disagree on the outcome');
        expect(decision.category, expectedCategory,
            reason: 'Dart and Python disagree on the category');
        expect(decision.language, expectedLanguage);
      });
    }
  });

  group('every stop-the-turn reply carries a real number', () {
    for (final category in [...rules.emergencyCategories, ...rules.refusalCategories]) {
      for (final language in ['en', 'bn']) {
        test('$category/$language', () {
          final text = referrals.responseFor(category, language);
          expect(text.trim(), isNotEmpty);
          expect(
            referrals.helplines.any((line) => text.contains(line.number)),
            isTrue,
            reason: 'no helpline number in $category/$language',
          );
        });
      }
    }
  });

  group('referral list matches the app', () {
    test('five national helplines, in order', () {
      expect(
        referrals.helplines.map((line) => line.number).toList(),
        ['999', '109', '16263', '1098', '333'],
      );
    });

    test('nine safeguarding focal points', () {
      expect(referrals.focalPoints.length, 9);
    });

    test('16263 is a health line and stays out of crisis scripts', () {
      final line = referrals.helpline('16263');
      expect(line.nameEn.toLowerCase(), contains('health'));
      expect(line.inEmergencyScript, isFalse);
      for (final category in rules.emergencyCategories) {
        for (final language in ['en', 'bn']) {
          expect(referrals.responseFor(category, language), isNot(contains('16263')));
        }
      }
    });

    test('suicide response puts 999 before Kaan Pete Roi', () {
      for (final language in ['en', 'bn']) {
        final text = referrals.responseFor('suicide_risk', language);
        expect(text.indexOf('999'),
            lessThan(text.indexOf(referrals.kaanPeteRoiNumber)),
            reason: '999 is the only 24/7 option and must come first');
      }
    });

    test('unknown numbers are not invented', () {
      expect(() => referrals.helpline('16430'), throwsArgumentError);
    });
  });

  group('offline behaviour', () {
    test('classification needs no network and no async', () {
      // If this ever becomes async, an emergency reply starts depending on
      // something that can hang. It must stay a synchronous, local call.
      final decision = rules.classify('he will kill me');
      expect(decision.kind, 'emergency');
      expect(referrals.responseFor(decision.category!, decision.language),
          contains('999'));
    });

    test('zero-width characters do not hide a disclosure', () {
      expect(rules.classify('আমাকে মার​ছে').kind, 'emergency');
      expect(rules.classify('I want‌ to die').kind, 'emergency');
    });
  });
}
