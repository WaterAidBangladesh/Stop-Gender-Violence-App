import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:ui';

class KnowledgeDetailScreen extends StatefulWidget {
  final String topicId;
  final String title;

  const KnowledgeDetailScreen({
    Key? key,
    required this.topicId,
    required this.title,
  }) : super(key: key);

  @override
  State<KnowledgeDetailScreen> createState() => _KnowledgeDetailScreenState();
}

class _KnowledgeDetailScreenState extends State<KnowledgeDetailScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  // ---------------- Safeguarding Sections ----------------
  final List<Map<String, String>> _safeguardingSections = [
    {
      "title": "What is Safeguarding?",
      "content":
      "Safeguarding means protecting people's health, wellbeing, and human rights so that everyone can live free from harm, abuse, neglect, and exploitation. "
          "It applies to children and adults alike, especially those who may be more vulnerable due to power imbalances or inequality.\n\n"
          "WaterAid adopts a zero-tolerance approach to all forms of abuse, and we are committed to creating a culture of safety, trust, and accountability across all areas of our work.",
    },
    {
      "title": "Core Principles of Safeguarding",
      "content":
      "1. **Protection** – Ensuring people are safe from harm, abuse, and exploitation.\n"
          "2. **Prevention** – Taking proactive steps to stop safeguarding incidents before they occur.\n"
          "3. **Empowerment** – Supporting individuals to understand their rights and to speak up safely.\n"
          "4. **Partnership** – Working collaboratively with communities and partners to uphold shared safeguarding standards.\n"
          "5. **Accountability** – Ensuring leaders, staff, and partners are responsible for promoting and maintaining a safe culture.\n"
          "6. **Survivor-Centred Approach** – Responding to concerns with dignity, respect, and care for those affected.",
    },
    {
      "title": "Why Safeguarding Matters",
      "content":
      "Safeguarding protects individuals and communities from harm and builds trust in the organisations that serve them. "
          "It ensures that everyone involved in WaterAid’s work—staff, partners, volunteers, and community members—is treated with respect and can raise concerns without fear. "
          "A strong safeguarding culture is essential for achieving WaterAid’s mission and upholding its values of integrity, inclusion, and accountability.",
    },
    {
      "title": "Everyday Examples of Safeguarding",
      "content":
      "- A community member safely reporting a safeguarding concern.\n"
          "- A teacher identifying and escalating signs of abuse.\n"
          "- Partners implementing safer recruitment and child protection policies.\n"
          "- Creating safe spaces for women, children, and marginalised groups.\n"
          "- Staff completing safeguarding training and modelling respectful behaviour.",
      "credit": "*Source: WaterAid Global Safeguarding Policy"
    },
  ];

  // ---------------- GBV Sections ----------------
  final List<Map<String, String>> _gbvSections = [
    {
      "title": "What is Gender-Based Violence?",
      "content":
      "Gender-Based Violence (GBV) refers to any act of physical, sexual, psychological, or economic harm directed against a person because of their gender. "
          "It is rooted in unequal power relations, social norms, and patriarchal structures that sustain gender discrimination. "
          "In the context of Bangladesh, GBV remains one of the most prevalent human rights violations, affecting women and girls disproportionately — "
          "through domestic abuse, early marriage, sexual harassment, and workplace exploitation. "
          "GBV is not confined to private spaces; it occurs at home, in public areas, and within institutions, reflecting the deep intersection between gender inequality, poverty, and social injustice.",
    },
    {
      "title": "Forms of GBV",
      "content":
      "1. Physical violence – beating, slapping, and physical assault.\n"
          "2. Sexual violence – rape, harassment, exploitation, and coercion.\n"
          "3. Psychological or emotional abuse – humiliation, threats, and intimidation.\n"
          "4. Economic violence – denial of financial rights, dowry-related abuse, and economic dependency.\n"
          "5. Harmful practices – early or forced marriage, and social exclusion based on gender.",
    },
    {
      "title": "Why Addressing GBV Matters",
      "content":
      "GBV violates fundamental human rights and undermines equality, dignity, and security. "
          "The MJF baseline survey revealed that violence not only causes physical and emotional suffering but also limits women’s mobility, economic participation, and social empowerment. "
          "It weakens community cohesion, perpetuates intergenerational cycles of abuse, and impedes national progress towards gender justice and sustainable development.",
    },
    {
      "title": "Everyday Examples of GBV",
      "content":
      "- Domestic violence and marital abuse\n"
          "- Early or forced marriage\n"
          "- Sexual harassment in public or workplaces\n"
          "- Denial of education or healthcare for girls\n"
          "- Psychological control or threats within families\n"
          "- Discrimination in wages, mobility, or decision-making",
      "credit": "*Source: Manusher Jonno Foundation (MJF)"
    },
  ];

  final List<Map<String, String>> _typesOfGbvSections = [
    {
      "title": "Types of Gender-Based Violence",
      "content":
      "Gender based violence manifests in multiple interlinked forms that often overlap in women’s lives. "
          "Recognizing these types is critical for developing effective prevention and response mechanisms:\n\n"
          "1. Physical Violence: Includes beating, slapping, or other forms of bodily harm.\n\n"
          "2. Sexual Violence: Encompasses rape, harassment, and unwanted sexual advances.\n\n"
          "3. Psychological or Emotional Violence: Refers to verbal abuse, intimidation, humiliation, and controlling behavior.\n\n"
          "4. Economic Violence: Involves restricting access to income, denying property or inheritance rights, and enforcing financial dependency.\n\n"
          "5. Harmful Traditional Practices: Includes early and forced marriage, dowry-related abuse, and other culturally sanctioned practices.",
      "credit": "*Source: Manusher Jonno Foundation (MJF)"
    },
  ];

  final List<Map<String, String>> _rolesAndResponsibilitiesSections = [
    {
      "title": "Roles & Responsibilities in Safeguarding",
      "content":
      "Safeguarding is a collective responsibility that requires active participation from all levels of society. Key roles include:\n\n"
          "- **Individuals:** Be vigilant and report any concerns or incidents of harm. Respect personal boundaries and contribute to creating safe environments.\n"
          "- **Community Leaders:** Raise awareness about safeguarding, model safe practices, and support community members in accessing help and protection.\n"
          "- **Organisations & Partners:** Develop and enforce safeguarding policies, provide regular training for staff and volunteers, ensure safe recruitment practices, and create mechanisms to report and respond to concerns effectively.\n"
          "- **Government & Authorities:** Establish and enforce laws and regulations that protect vulnerable people, fund services such as shelters, hotlines, and counselling, and monitor compliance with safeguarding standards.\n\n"
          "By fulfilling these responsibilities, everyone contributes to a culture of safety, trust, and accountability, ensuring that vulnerable people are protected and can thrive.",
      "credit": "*Source: WaterAid Global Safeguarding Framework 2023-2028"
    },
  ];

  final List<Map<String, String>> _reportingMechanismsSections = [
    {
      "title": "Reporting Mechanisms",
      "content":
      "Reporting is the first step towards safety and justice:\n\n"
          "How to Report:\n"
          "- Anonymous reporting through apps or hotlines.\n"
          "- Direct reporting to safeguarding focal points or authorities.\n\n"
          "Include in Report:\n"
          "- Date, time, and location.\n"
          "- Description of what happened.\n"
          "- Any evidence or witness details.",
      "credit": "*Source: WaterAid Global Safeguarding Policy"
    },
  ];

  final List<Map<String, String>> _preventionGbvSections = [
    {
      "title": "Prevention of Gender-Based Violence",
      "content":
      "Prevention must go beyond awareness—it requires transforming social norms, strengthening institutions, and empowering individuals and communities.\n\n"
          "Key prevention strategies include education, women’s empowerment, community engagement, legal strengthening, workplace/public space safety, bystander action, and media advocacy.",
      "credit": "*Source: Manusher Jonno Foundation (MJF)"
    },
  ];

  final List<Map<String, String>> _mythsFactsSections = [
    {
      "title": "Myths vs. Facts about Gender-Based Violence",
      "content":
      "Persistent myths and misconceptions continue to normalize and excuse GBV. Dispelling these myths is key to building awareness, empathy, and accountability.\n\n"
          "Myth: Gender-Based Violence only happens to women.\n"
          "Fact: While women and girls are disproportionately affected, GBV can impact anyone—including men, boys, and gender-diverse individuals.\n\n"
          "Myth: GBV is a private issue that should stay within the family.\n"
          "Fact: GBV is a violation of human rights and a criminal offense.\n\n"
          "Myth: Survivors provoke or deserve the violence.\n"
          "Fact: Responsibility always lies with the perpetrator.\n\n"
          "Myth: Only physical assault qualifies as GBV.\n"
          "Fact: GBV includes emotional, psychological, economic, and sexual abuse.\n\n"
          "Myth: Reporting GBV ruins family reputation.\n"
          "Fact: Silence perpetuates harm.",
      "credit": "*Source: Manusher Jonno Foundation (MJF)"
    },
  ];

  final List<Map<String, String>> _safeguardingPrinciplesSections = [
    {
      "title": "Safeguarding Principles",
      "content":
      "1. Do No Harm: Protect individuals at all times.\n"
          "2. Confidentiality: Keep personal information private.\n"
          "3. Survivor-Centered Approach: Respect choices, ensure dignity.\n"
          "4. Accountability: Be transparent and responsible.\n"
          "5. Non-Discrimination: Treat everyone equally and fairly.",
      "credit": "*Source: WaterAid Global Safeguarding Policy"
    },
  ];

  // ---------------- Utility: Fullscreen Viewer ----------------
  void _openImageGallery(BuildContext context, int initialIndex) {
    showDialog(
      context: context,
      barrierColor: Colors.black.withOpacity(0.8),
      builder: (context) {
        int currentIndex = initialIndex;
        return StatefulBuilder(
          builder: (context, setState) {
            return Stack(
              children: [
                Center(
                  child: Image.asset(
                    'assets/pdf${currentIndex + 1}.jpg',
                    fit: BoxFit.contain,
                  ),
                ),
                if (currentIndex > 0)
                  Positioned(
                    left: 20,
                    top: MediaQuery.of(context).size.height / 2 - 30,
                    child: IconButton(
                      icon: const Icon(Icons.arrow_back_ios,
                          size: 40, color: Colors.white),
                      onPressed: () {
                        setState(() => currentIndex--);
                      },
                    ),
                  ),
                if (currentIndex < 24)
                  Positioned(
                    right: 20,
                    top: MediaQuery.of(context).size.height / 2 - 30,
                    child: IconButton(
                      icon: const Icon(Icons.arrow_forward_ios,
                          size: 40, color: Colors.white),
                      onPressed: () {
                        setState(() => currentIndex++);
                      },
                    ),
                  ),
                Positioned(
                  top: 40,
                  right: 20,
                  child: IconButton(
                    icon: const Icon(Icons.close,
                        size: 35, color: Colors.white),
                    onPressed: () => Navigator.pop(context),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    late List<Map<String, String>> sections;
    late Color bgColor;
    late String headerImage;
    late bool isSafeguarding;

    switch (widget.topicId) {
      case "1":
        sections = _safeguardingSections;
        bgColor = const Color(0xFFA9C2E9);
        isSafeguarding = true;
        headerImage = "assets/safework.png"; // ✅ Changed here
        break;
      case "2":
        sections = _gbvSections;
        bgColor = const Color(0xFF29327D);
        isSafeguarding = false;
        headerImage = "assets/gbvbg.jpg";
        break;
      case "3":
        sections = _typesOfGbvSections;
        bgColor = const Color(0xFFE85C4B);
        isSafeguarding = false;
        headerImage = "assets/3.jpg";
        break;
      case "4":
        sections = _rolesAndResponsibilitiesSections;
        bgColor = const Color(0xFF00A2AD);
        isSafeguarding = false;
        headerImage = "assets/4.jpg";
        break;
      case "5":
        sections = _reportingMechanismsSections;
        bgColor = const Color(0xFF662581);
        isSafeguarding = false;
        headerImage = "assets/5.jpg";
        break;
      case "6":
        sections = _preventionGbvSections;
        bgColor = const Color(0xFF763048);
        isSafeguarding = false;
        headerImage = "assets/6.jpg";
        break;
      case "7":
        sections = _mythsFactsSections;
        bgColor = const Color(0xFF5D657C);
        isSafeguarding = false;
        headerImage = "assets/7.jpg";
        break;
      case "8":
        sections = _safeguardingPrinciplesSections;
        bgColor = const Color(0xFF432467);
        isSafeguarding = false;
        headerImage = "assets/8.jpg";
        break;
      default:
        sections = [];
        bgColor = Colors.white;
        isSafeguarding = false;
        headerImage = "";
    }

    return Scaffold(
      backgroundColor: bgColor,
      appBar: AppBar(
        backgroundColor: bgColor,
        elevation: 0,
        title: Text(widget.title),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // ✅ Now single header image like all other sections
            Image.asset(
              headerImage,
              width: double.infinity,
              height: 350,
              fit: BoxFit.cover,
              errorBuilder: (context, error, stackTrace) =>
                  Container(height: 200, color: Colors.grey[300]),
            ),
            const SizedBox(height: 16),

            // --------- One Single Card with all content ----------
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Card(
                color: Colors.white,
                elevation: 4,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: sections.map((section) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(section["title"]!,
                                style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            Text(section["content"]!,
                                style: const TextStyle(fontSize: 14)),
                            if (section.containsKey("credit"))
                              Padding(
                                padding: const EdgeInsets.only(top: 8),
                                child: Align(
                                  alignment: Alignment.bottomRight,
                                  child: Text(
                                    section["credit"]!,
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontStyle: FontStyle.italic,
                                      color: Colors.grey[600],
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // ---------------- PDF Gallery only for Safeguarding ----------------
            if (isSafeguarding)
              SizedBox(
                height: 200,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  itemCount: 25,
                  itemBuilder: (context, index) {
                    return GestureDetector(
                      onTap: () => _openImageGallery(context, index),
                      child: Container(
                        margin: const EdgeInsets.symmetric(horizontal: 8),
                        child: Image.asset(
                          'assets/pdf${index + 1}.jpg',
                          width: 250,
                          height: 200,
                          fit: BoxFit.cover,
                        ),
                      ),
                    );
                  },
                ),
              ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
