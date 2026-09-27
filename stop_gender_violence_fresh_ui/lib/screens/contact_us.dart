import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class ContactUsPage extends StatelessWidget {
  const ContactUsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF7e2c76),
      appBar: AppBar(
        title: const Text(
          "Contact Us",
          style: TextStyle(color: Colors.white),
        ),
        backgroundColor: const Color(0xFF7e2c76),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 10),
            const Text(
              "We are committed to promoting a safe, inclusive, and respectful environment for everyone, free from all forms of gender-based violence, abuse, harassment, or exploitation. Our safeguarding approach prioritises the dignity, rights, and wellbeing of every individual involved in our activities — including participants, staff, volunteers, and partners.",
              style: TextStyle(color: Colors.white70, fontSize: 16),
            ),
            const SizedBox(height: 12),
            const Text(
              "We maintain zero tolerance for any behaviour that undermines safety, equality, or respect. Any form of sexual misconduct, discrimination, or misuse of power will not be accepted. We encourage everyone to speak up and report safeguarding or gender-based violence concerns confidentially to the designated team, ensuring prompt and appropriate action to protect those affected.",
              style: TextStyle(color: Colors.white70, fontSize: 16),
            ),
            const SizedBox(height: 20),

            const Text(
              "To get in touch:",
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 10),

            contactItem("Email", "safeguardwab@wateraid.org"),
          ],
        ),
      ),
    );
  }

  /// Widget for Contact Items
  static Widget contactItem(String title, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: RichText(
        text: TextSpan(
          children: [
            TextSpan(
              text: "$title: ",
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
            WidgetSpan(
              child: GestureDetector(
                onTap: () async {
                  final Uri emailLaunchUri = Uri(
                    scheme: 'mailto',
                    path: value,
                  );
                  if (await canLaunchUrl(emailLaunchUri)) {
                    await launchUrl(emailLaunchUri);
                  }
                },
                child: Text(
                  value,
                  style: const TextStyle(
                    color: Colors.lightBlueAccent,
                    fontSize: 16,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
