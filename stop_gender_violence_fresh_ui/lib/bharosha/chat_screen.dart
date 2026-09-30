/// Bharosha's chat screen.
///
/// DEVICE SAFETY, because the phone in her hand may not be private:
///
///  * FLAG_SECURE while this screen is open — no screenshots, no screen
///    recording, and no thumbnail in the recent-apps switcher.
///  * A quick-exit control in the app bar that clears the conversation and closes
///    the app, reachable in one tap from anywhere on the screen.
///  * Nothing is persisted. Messages live in this widget's state and go when it
///    is disposed. There is no database, no shared_preferences, no file.
///  * No notifications of any kind from this feature.
///  * No file or image upload.
///  * No login. Requiring an account to ask for help is a barrier at the worst
///    possible moment, and it would tie the questions to an identity.
///
/// WHAT WORKS OFFLINE: emergency and refusal detection, and every referral. Those
/// are matched on the device against bundled rules, so a woman with no signal, or
/// whose server has gone to sleep, still gets 999 and 109 instantly. Only
/// explanatory answers need the network, and when it is unreachable the screen
/// falls back to the same local referral text rather than an error.

import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';

import 'client.dart';
import 'referrals.dart';
import 'rules_loader.dart';

const _secureWindowChannel =
    MethodChannel('com.wateraidbd.shomotashurokkha/secure_window');

/// UI chrome only. Everything a person in danger reads — every referral, every
/// refusal — comes from the shared referrals.json, not from here.
const Map<String, Map<String, String>> _ui = {
  'en': {
    'title': 'Bharosha',
    'subtitle': 'Safeguarding guidance',
    'disclaimer':
        'Bharosha explains WaterAid’s safeguarding material and points you to people who can help. '
        'It is not counselling, legal advice, or a way to report an incident. '
        'In an emergency call 999.',
    'hint': 'Ask about safeguarding or gender-based violence',
    'send': 'Send',
    'exit': 'Leave now',
    'exitTooltip': 'Clear this conversation and close the app',
    'thinking': 'Looking in WaterAid’s material…',
    'greeting':
        'Hello. You can ask me about safeguarding and gender-based violence, and I will answer from WaterAid’s own material.\n\n'
        'If you are in danger right now, do not wait for me — call **999**.',
    'notSaved': 'This conversation is not saved. It disappears when you leave.',
  },
  'bn': {
    'title': 'ভরসা',
    'subtitle': 'সুরক্ষা বিষয়ক দিশা',
    'disclaimer':
        'ভরসা ওয়াটারএইডের সেফগার্ডিং উপকরণ ব্যাখ্যা করে এবং সাহায্য করতে পারেন এমন মানুষের কাছে পথ দেখায়। '
        'এটি কাউন্সেলিং, আইনি পরামর্শ বা ঘটনা রিপোর্ট করার মাধ্যম নয়। '
        'জরুরি অবস্থায় ৯৯৯ (999) নম্বরে কল করুন।',
    'hint': 'সেফগার্ডিং বা জেন্ডারভিত্তিক সহিংসতা নিয়ে জিজ্ঞেস করুন',
    'send': 'পাঠান',
    'exit': 'এখনই বেরিয়ে যান',
    'exitTooltip': 'এই কথাবার্তা মুছে অ্যাপ বন্ধ করুন',
    'thinking': 'ওয়াটারএইডের উপকরণে খুঁজছি…',
    'greeting':
        'নমস্কার। সেফগার্ডিং ও জেন্ডারভিত্তিক সহিংসতা নিয়ে আমাকে জিজ্ঞেস করতে পারেন; আমি ওয়াটারএইডের নিজস্ব উপকরণ থেকে উত্তর দেব।\n\n'
        'আপনি যদি এখনই বিপদে থাকেন, আমার জন্য অপেক্ষা করবেন না — **999** নম্বরে কল করুন।',
    'notSaved': 'এই কথাবার্তা সংরক্ষণ করা হয় না। আপনি বেরিয়ে গেলেই মুছে যায়।',
  },
};

String _t(String language, String key) => _ui[language]![key]!;

class _Message {
  _Message.user(this.text)
      : isUser = true,
        kind = 'question';
  _Message.bot(this.text, this.kind) : isUser = false;

  final String text;
  final bool isUser;

  /// How the reply was produced: 'emergency', 'refusal', 'answer',
  /// 'no_context', 'unreachable'. Drives the colour of the bubble, so an
  /// emergency referral does not look like a chat message.
  final String kind;
}

class BharoshaChatScreen extends StatefulWidget {
  const BharoshaChatScreen({Key? key}) : super(key: key);

  @override
  State<BharoshaChatScreen> createState() => _BharoshaChatScreenState();
}

class _BharoshaChatScreenState extends State<BharoshaChatScreen> {
  static const Color _brand = Color(0xFF5E2A8E);

  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _client = BharoshaClient();
  final List<_Message> _messages = [];

  late String _sessionId;
  String _language = 'en';
  BharoshaRules? _rules;
  bool _waiting = false;

  @override
  void initState() {
    super.initState();
    _sessionId = newSessionId();
    _setSecure(true);
    _language = _deviceLanguage();
    _loadRules();
  }

  String _deviceLanguage() {
    // Bangla for a Bangla device, without touching the app's unused
    // LanguageProvider. The toggle in the app bar overrides it.
    final locale = WidgetsBinding.instance.platformDispatcher.locale;
    return locale.languageCode == 'bn' ? 'bn' : 'en';
  }

  Future<void> _loadRules() async {
    final rules = await BharoshaRules.load();
    if (!mounted) return;
    setState(() {
      _rules = rules;
      _messages.add(_Message.bot(_t(_language, 'greeting'), 'greeting'));
    });
  }

  Future<void> _setSecure(bool on) async {
    if (defaultTargetPlatform != TargetPlatform.android) return;
    try {
      await _secureWindowChannel.invokeMethod(on ? 'enable' : 'disable');
    } on PlatformException {
      // An older build without the channel: the screen still works, it just is
      // not hidden from the app switcher. Not worth blocking her on.
    } on MissingPluginException {
      // Same.
    }
  }

  @override
  void dispose() {
    // No persistence: the conversation exists only here, and this is where it
    // ends. The server is told to forget it too, though it expires anyway.
    _messages.clear();
    _client.forget(_sessionId);
    _client.close();
    _setSecure(false);
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  /// Clear the conversation and close the app.
  ///
  /// Not "go to the home screen": the app itself should not be sitting in front
  /// of whoever picks up the phone next, and with FLAG_SECURE set there is no
  /// preview of it in the switcher either.
  Future<void> _leaveNow() async {
    setState(() => _messages.clear());
    _client.forget(_sessionId);
    await _setSecure(false);
    await SystemNavigator.pop();
  }

  Future<void> _send() async {
    final question = _input.text.trim();
    final rules = _rules;
    if (question.isEmpty || rules == null || _waiting) return;

    _input.clear();
    final decision = rules.safety.classify(question);

    setState(() {
      _messages.add(_Message.user(question));
      // Answer in the language she wrote in, whatever the toggle says.
      _language = decision.language;
    });
    _scrollToEnd();

    // THE FIVE EMERGENCIES, AND ONLY THOSE, are answered here: bundled text,
    // no request, no model, no wait. A model call for "he is going to kill
    // me" would mean seconds instead of milliseconds and a network she may
    // not have.
    if (decision.stopsTurn) {
      setState(() {
        _messages.add(_Message.bot(
          rules.referrals.responseFor(decision.category!, decision.language),
          _bubbleKindFor(decision.kind),
        ));
      });
      _scrollToEnd();
      return;
    }

    // EVERY OTHER CATEGORY — a disclosure, a refusal, low distress, a
    // greeting — is still recognised here, but the model writes the reply
    // and the server appends the referral block. SAFETY DECIDES, THE AI
    // SPEAKS. The category travels with the message; the server re-classifies
    // and trusts only itself.
    //
    // The wait is capped at eight seconds for a recognised category, because
    // the bundled text is a complete, reviewed reply and she should not sit
    // watching a spinner for it. An unrecognised question keeps the longer
    // timeout: there is no bundled text to fall back to, and a real answer
    // from the corpus is worth waiting for.
    final recognised = decision.category != null;
    setState(() => _waiting = true);
    final reply = await _client.ask(
      sessionId: _sessionId,
      query: question,
      category: decision.category,
      timeout: recognised ? const Duration(seconds: 8) : null,
    );
    if (!mounted) return;

    setState(() {
      _waiting = false;
      if (reply.kind == 'unreachable' && recognised) {
        // Timed out, offline, or the server is asleep: the bundled text for
        // the category, exactly as before the model was involved. It is not
        // a consolation prize — it is the complete, reviewed reply with every
        // number in it. The floor did not move.
        _messages.add(_Message.bot(
          rules.referrals.responseFor(decision.category!, decision.language),
          _bubbleKindFor(decision.kind),
        ));
      } else if (reply.kind == 'unreachable') {
        // Its own message, NOT the no-context one. "I don't have reliable
        // information about that" is a claim about her question; the truth here
        // is that the question was never asked, because the service could not be
        // reached. Saying the first when the second is true tells her the app has
        // no answer for her when in fact it never looked.
        _messages.add(_Message.bot(
          rules.referrals.responseFor('unreachable', decision.language),
          'unreachable',
        ));
      } else {
        // Styled by KIND, the same mapping the local path uses, so a disclosure
        // answered by the server looks like a disclosure answered on the
        // device rather than like an ordinary reply.
        _messages.add(_Message.bot(reply.text, _bubbleKindFor(reply.kind)));
      }
    });
    _scrollToEnd();
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _dial(String number) async {
    final uri = Uri.parse('tel:$number');
    if (await canLaunchUrl(uri)) await launchUrl(uri);
  }

  @override
  Widget build(BuildContext context) {
    final rules = _rules;
    return Scaffold(
      backgroundColor: const Color(0xFFF4F1F8),
      appBar: AppBar(
        backgroundColor: _brand,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_t(_language, 'title'),
                style: const TextStyle(color: Colors.white, fontSize: 18)),
            Text(_t(_language, 'subtitle'),
                style: const TextStyle(color: Colors.white70, fontSize: 12)),
          ],
        ),
        actions: [
          // Language toggle. Deliberately not wired to the app's unused
          // LanguageProvider, which is out of scope here.
          TextButton(
            onPressed: () => setState(
                () => _language = _language == 'bn' ? 'en' : 'bn'),
            child: Text(
              _language == 'bn' ? 'EN' : 'বাংলা',
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
          ),
          Tooltip(
            message: _t(_language, 'exitTooltip'),
            child: IconButton(
              icon: const Icon(Icons.exit_to_app, color: Colors.white),
              onPressed: _leaveNow,
            ),
          ),
        ],
      ),
      body: rules == null
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _disclaimer(),
                Expanded(
                  child: ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.all(12),
                    itemCount: _messages.length + (_waiting ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == _messages.length) return _thinking();
                      return _bubble(_messages[index]);
                    },
                  ),
                ),
                _quickNumbers(rules.referrals),
                _composer(),
              ],
            ),
    );
  }

  Widget _disclaimer() => Container(
        width: double.infinity,
        color: const Color(0xFFEDE4F5),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_t(_language, 'disclaimer'),
                style: const TextStyle(fontSize: 12, color: Color(0xFF3F2A55))),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(Icons.lock_outline, size: 12, color: Color(0xFF6B5A7D)),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(_t(_language, 'notSaved'),
                      style: const TextStyle(
                          fontSize: 11, color: Color(0xFF6B5A7D))),
                ),
              ],
            ),
          ],
        ),
      );

  /// The two numbers that matter, always on screen, one tap from the dialer —
  /// so she never has to read a message to find them.
  Widget _quickNumbers(Referrals referrals) {
    final emergency = referrals.helpline('999');
    final vawc = referrals.helpline('109');
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      child: Row(
        children: [
          for (final line in [emergency, vawc])
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: OutlinedButton.icon(
                  onPressed: () => _dial(line.number),
                  icon: const Icon(Icons.phone, size: 16, color: Color(0xFF1B7A5A)),
                  label: Text(
                    line.number,
                    style: const TextStyle(
                        color: Color(0xFF1B7A5A), fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _thinking() => Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 10),
            Text(_t(_language, 'thinking'),
                style: const TextStyle(color: Colors.black54, fontSize: 13)),
          ],
        ),
      );

  /// How a locally answered turn should LOOK, which is not the same question as
  /// what it says.
  ///
  /// Three appearances, not seven. A social reply or a clarifying question must
  /// look like ordinary conversation — putting a red emergency edge on "hello"
  /// is the visual version of the mistake this whole tier was built to fix.
  static String _bubbleKindFor(String kind) {
    switch (kind) {
      // She has told the app something difficult. Styled like an emergency and
      // not like a refusal, so the reply looks like it was taken seriously
      // rather than like a decline.
      case 'emergency':
      case 'disclosure':
        return 'emergency';
      // A refusal, and a third-party concern: both hand over numbers and both
      // say what this app will not do. Serious, but not an alarm.
      case 'refuse':
      case 'third_party':
        return 'refusal';
      // 'social', 'vague' and 'low_distress' — plain, like any other reply.
      // low_distress especially: someone who wrote "mon kharap" should not
      // have a red emergency edge drawn around the answer to it.
      default:
        return 'greeting';
    }
  }

  Widget _bubble(_Message message) {
    // An emergency referral must not look like conversation: red edge, full
    // width, so it reads as the app handing over a phone number.
    final isEmergency = message.kind == 'emergency';
    final isRefusal = message.kind == 'refusal';
    final background = message.isUser
        ? _brand
        : isEmergency
            ? const Color(0xFFFDECEC)
            : Colors.white;

    return Align(
      alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * (message.isUser ? 0.78 : 0.94),
        ),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
          border: isEmergency
              ? const Border(left: BorderSide(color: Color(0xFFA81E24), width: 4))
              : isRefusal
                  ? const Border(left: BorderSide(color: Color(0xFF8A5200), width: 4))
                  : null,
        ),
        child: message.isUser
            ? Text(message.text, style: const TextStyle(color: Colors.white))
            : MarkdownBody(
                data: message.text,
                selectable: true,
                styleSheet: MarkdownStyleSheet(
                  p: const TextStyle(fontSize: 14.5, height: 1.45),
                  strong: const TextStyle(fontWeight: FontWeight.bold),
                  listBullet: const TextStyle(fontSize: 14.5),
                ),
              ),
      ),
    );
  }

  Widget _composer() => Container(
        color: Colors.white,
        padding: const EdgeInsets.fromLTRB(12, 6, 8, 10),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _input,
                minLines: 1,
                maxLines: 4,
                maxLength: 2000,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: InputDecoration(
                  counterText: '',
                  hintText: _t(_language, 'hint'),
                  hintStyle: const TextStyle(fontSize: 13),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                  ),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
            ),
            // No attachment button, by design: no file or image upload.
            IconButton(
              icon: const Icon(Icons.send, color: _brand),
              onPressed: _send,
              tooltip: _t(_language, 'send'),
            ),
          ],
        ),
      );
}
