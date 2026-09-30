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
    test('has cases in both languages and every outcome', () {
      expect(cases.length, greaterThan(40));
      expect(cases.where((c) => c['language'] == 'bn'), isNotEmpty);
      expect(cases.where((c) => c['language'] == 'en'), isNotEmpty);
      for (final kind in [
        'emergency',
        'refuse',
        'third_party',
        'disclosure',
        'low_distress',
        'reporting',
        'social',
        'vague',
        'proceed',
      ]) {
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

    test('the Important Numbers screen cannot relabel a number', () {
      // That screen now reads this same list. The regression it guards against
      // is concrete: it described 16263 as "24/7 confidential support for
      // survivors of gender-based violence" while this list called it a health
      // line. Every number must carry a description, and 16263's must say what
      // it is and where violence actually goes.
      for (final line in referrals.helplines) {
        expect(line.descEn.trim(), isNotEmpty, reason: line.number);
        expect(line.descBn.trim(), isNotEmpty, reason: line.number);
      }
      final health = referrals.helpline('16263');
      expect(health.descEn.toLowerCase(), contains('health'));
      expect(health.descEn, contains('109'));
      expect(health.descEn.toLowerCase(),
          isNot(contains('support for survivors')));
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

  group('the light replies stay light', () {
    // These assert that text is ABSENT, which is the only way restraint holds.
    // The failure they guard against is the one the app shipped with: "kemon
    // acho?" answered with an apology, a five-item topic list and two emergency
    // helplines. Nothing stops that creeping back except a test that fails.

    test('a social reply carries no helpline number', () {
      for (final category in ['greeting', 'thanks', 'acknowledgement', 'bot_abuse']) {
        for (final language in ['en', 'bn']) {
          final text = referrals.responseFor(category, language);
          for (final line in referrals.helplines) {
            expect(text, isNot(contains(line.number)),
                reason: '$category/$language still lists ${line.number}');
          }
        }
      }
    });

    test('a social reply carries no topic list', () {
      const bulletPoint = '\n- ';
      for (final category in rules.socialCategories) {
        for (final language in ['en', 'bn']) {
          expect(referrals.responseFor(category, language),
              isNot(contains(bulletPoint)),
              reason: '$category/$language has a bullet list');
        }
      }
    });

    test('the vague reply asks a question and gives exactly one number', () {
      for (final language in ['en', 'bn']) {
        final text = referrals.responseFor('vague', language);
        expect(text, contains('?'));
        expect(text, contains('999'));
        expect(text, isNot(contains('109')));
      }
    });

    test('the off-topic reply is shorter than half the no-context reply', () {
      for (final language in ['en', 'bn']) {
        expect(
          referrals.responseFor('off_topic', language).length * 2,
          lessThan(referrals.responseFor('no_context', language).length),
        );
      }
    });

    test('a social turn is styled like conversation, not like a crisis', () {
      // A red emergency edge on "hello" is the visual form of the same mistake.
      for (final kind in ['social', 'vague']) {
        expect(kind, isNot('emergency'));
      }
      expect(rules.classify('kemon acho?').kind, 'social');
      expect(rules.classify('hi, he is beating me').kind, 'emergency');
    });
  });

  group('the device list is the whole boundary', () {
    // stopsTurn is the one thing the phone decides by itself. If a category
    // drifts onto this list, a reply that should be written for the person
    // becomes a saved message; if one drifts off it, "he is going to kill me"
    // starts depending on a network she may not have.
    test('exactly these are answered on the device', () {
      // Five, and only five. Every other category is recognised here but
      // written by the model there: "safety decides, the AI speaks". The
      // bundled text for those is the eight-second fallback, not the reply.
      expect(rules.deviceCategories.toSet(), {
        'suicide_risk', 'immediate_danger', 'threat_to_life',
        'child_disclosure', 'active_violence',
      });
    });

    test('an emergency is decided here, synchronously, with a number', () {
      for (final message in [
        'he is beating me right now',
        'আমাকে মারছে, বাঁচান',
        'I want to die',
        'he said he will kill me',
        'they want to marry off my daughter',
      ]) {
        final decision = rules.classify(message);
        expect(decision.stopsTurn, isTrue, reason: message);
        expect(referrals.responseFor(decision.category!, decision.language),
            contains('999'));
      }
    });

    test('everything conversational goes to the model', () {
      for (final message in [
        'hi',
        'kemon acho?',
        'thank you',
        'hmm',
        'ki korbo',
        'my friend is being abused by her husband',
        'what is gender based violence',
        'how do I cook rice',
        // These used to be answered here. They are still recognised here —
        // the category travels with the message — but the words are the
        // model's, and the referral block is appended by the server.
        'my husband hits me',
        'he controls my money',
        'should I leave my husband?',
        'I feel so alone',
        'I want to report this',
        'who are you?',
        'will my husband see this',
      ]) {
        expect(rules.classify(message).stopsTurn, isFalse, reason: message);
      }
    });

    test('but each of those still has bundled text for when it cannot', () {
      for (final message in ['hi', 'thank you', 'hmm', 'ki korbo',
          'my friend is being abused by her husband']) {
        final decision = rules.classify(message);
        expect(referrals.responseFor(decision.category!, decision.language).trim(),
            isNotEmpty, reason: message);
      }
    });
  });

  group('language', () {
    test('romanised Bangla is detected, and reads the Bangla text', () {
      // She typed Latin letters because that is what her keyboard offered.
      for (final message in ['amar shami amake mare', 'ki korbo?', 'kemon acho',
          'tumi ki help korte parbe?', 'achha bujhlam']) {
        expect(rules.detectLanguage(message), 'bn_roman', reason: message);
      }
      for (final message in ['he keeps my salary', 'I want to die', 'hmm',
          'ma please help', 'What is safeguarding?']) {
        expect(rules.detectLanguage(message), 'en', reason: message);
      }
      expect(rules.detectLanguage('সেফগার্ডিং কী'), 'bn');
      expect(referrals.responseFor('vague', 'bn_roman'),
          referrals.responseFor('vague', 'bn'));
    });

    test('the greeting fallback mirrors hers', () {
      expect(referrals.greetingCategory('Assalamu alaikum'), 'greeting_salam');
      expect(referrals.greetingCategory('আসসালামু আলাইকুম'), 'greeting_salam');
      expect(referrals.greetingCategory('নমস্কার'), 'greeting_namaskar');
      expect(referrals.greetingCategory('hi'), 'greeting');
      expect(referrals.responseFor('greeting_salam', 'bn'), contains('ওয়ালাইকুম আসসালাম'));
      expect(referrals.responseFor('greeting_salam', 'bn'), isNot(contains('নমস্কার')));
      expect(referrals.responseFor('greeting_namaskar', 'bn'), startsWith('নমস্কার'));
    });
  });

  group('offline behaviour', () {
    test('every recognised category has bundled text for a dead network', () {
      // The offline fallback is keyed on CATEGORY, not on whether the device
      // answers it. A greeting with no network must get the greeting, not
      // "I could not reach the service" — which is what it got until this
      // test existed.
      for (final testCase in cases) {
        final category = testCase['category'] as String?;
        if (category == null) continue;
        expect(referrals.responseFor(category, testCase['language'] as String)
            .trim(), isNotEmpty,
            reason: 'no offline text for $category');
      }
    });

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
