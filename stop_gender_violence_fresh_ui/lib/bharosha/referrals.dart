/// Referral contacts and the hardcoded responses that carry them, on the device.
///
/// This is the single source of truth for the app's contact list as well as for
/// Bharosha's replies: `emergency_contacts_screen.dart` reads it too, so there is
/// no second copy of a helpline number anywhere in the project. A referral number
/// that does not answer is worse than no app at all, and two lists would
/// eventually disagree about which numbers those are.
///
/// Generated from the Python source into assets/bharosha/referrals.json by
/// bharosha_service/tools/export_shared.py. Every string a frightened person
/// might read is written by hand there, in both languages — none of it is
/// generated, retrieved, or machine-translated at runtime.

import 'dart:convert';

class Helpline {
  const Helpline({
    required this.number,
    required this.nameEn,
    required this.nameBn,
    required this.inEmergencyScript,
  });

  final String number;
  final String nameEn;
  final String nameBn;

  /// False keeps a number out of the crisis scripts while it stays visible in
  /// the contacts list. 16263 is the case: confirmed as Shastho Batayon, the
  /// national health line, not the GBV hotline the app used to label it.
  final bool inEmergencyScript;

  String name(String language) => language == 'bn' ? nameBn : nameEn;
}

class FocalPoint {
  const FocalPoint({
    required this.organisation,
    required this.number,
    required this.email,
  });

  final String organisation;
  final String number;
  final String email;
}

class Referrals {
  Referrals._({
    required this.helplines,
    required this.focalPoints,
    required this.safeguardingEmail,
    required this.kaanPeteRoiNumber,
    required Map<String, Map<String, String>> responses,
    required Map<String, String> footers,
  })  : _responses = responses,
        _footers = footers;

  final List<Helpline> helplines;
  final List<FocalPoint> focalPoints;
  final String safeguardingEmail;

  /// Bangladesh's emotional support and suicide prevention line. Note it runs
  /// 3pm–3am, NOT 24/7 — the hours are written into the suicide-risk response
  /// itself so nobody dials at 9am expecting an answer.
  final String kaanPeteRoiNumber;

  final Map<String, Map<String, String>> _responses;
  final Map<String, String> _footers;

  factory Referrals.fromJson(String source) {
    final data = jsonDecode(source) as Map<String, dynamic>;

    return Referrals._(
      helplines: [
        for (final line in (data['national_helplines'] as List))
          Helpline(
            number: line['number'] as String,
            nameEn: line['name_en'] as String,
            nameBn: line['name_bn'] as String,
            inEmergencyScript: line['in_emergency_script'] as bool,
          ),
      ],
      focalPoints: [
        for (final point in (data['safeguarding_focal_points'] as List))
          FocalPoint(
            organisation: point['organisation'] as String,
            number: point['number'] as String,
            email: point['email'] as String,
          ),
      ],
      safeguardingEmail: data['safeguarding_email'] as String,
      kaanPeteRoiNumber:
          (data['kaan_pete_roi'] as Map<String, dynamic>)['number'] as String,
      responses: {
        for (final entry in (data['responses'] as Map<String, dynamic>).entries)
          entry.key: (entry.value as Map<String, dynamic>).cast<String, String>(),
      },
      footers: (data['answer_footer'] as Map<String, dynamic>)
          .cast<String, String>(),
    );
  }

  /// The hardcoded reply for a safety category, in `en` or `bn`.
  ///
  /// Falls back to English rather than throwing: a missing translation must
  /// still put a phone number in front of someone.
  String responseFor(String category, String language) {
    final byLanguage = _responses[category];
    if (byLanguage == null) {
      throw ArgumentError('no hardcoded response for category "$category"');
    }
    return byLanguage[language] ?? byLanguage['en']!;
  }

  /// Appended to answers the server generates. The model is forbidden from
  /// writing phone numbers — a hallucinated digit in a helpline number is one of
  /// the worst failures this app could have — so they come from here.
  String answerFooter(String language) => _footers[language] ?? _footers['en']!;

  Helpline helpline(String number) => helplines.firstWhere(
        (line) => line.number == number,
        orElse: () => throw ArgumentError(
          '$number is not in the referral list; numbers are not invented here',
        ),
      );
}
