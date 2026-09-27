import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:firebase_auth/firebase_auth.dart';

class EmergencyContactsScreen extends StatefulWidget {
  const EmergencyContactsScreen({Key? key}) : super(key: key);

  @override
  State<EmergencyContactsScreen> createState() =>
      _EmergencyContactsScreenState();
}

class _EmergencyContactsScreenState extends State<EmergencyContactsScreen> {
  final List<Map<String, String>> importantNumbers = [
    {
      'num': '999',
      'title': 'National Emergency Services',
      'desc':
      'A free 24/7 emergency helpline connecting you to police, fire, and ambulance services across the country. Immediate assistance for accidents, crimes, fires, or medical emergencies.'
    },
    {
      'num': '109',
      'title': 'Women & Children National Help Line',
      'desc':
      'A national multi-sectoral helpline offering 24/7 support for women and children facing abuse, violence, or exploitation. Provides counselling, legal guidance, and referrals to protection and social services.'
    },
    {
      'num': '16263',
      'title': 'Gender Based Violence Hotline',
      'desc':
      '24/7 confidential support for survivors of gender-based violence, including counselling, guidance, and referrals to medical, legal, and social services.'
    },
    {
      'num': '1098',
      'title': 'Child Help Line',
      'desc':
      'A free 24/7 helpline for children facing abuse, violence, exploitation, or neglect. Offers confidential support, counselling, and connects children with protection services and emergency assistance.'
    },
    {
      'num': '333',
      'title': 'Citizen Service',
      'desc':
      'A government helpline providing information, guidance, and assistance on public services, complaints, and social issues. Available 24/7 for quick and reliable citizen support.'
    },
  ];

  final List<Map<String, String>> safeguardingNumbers = [
    {
      'num': '01717070777',
      'org': 'Dushtha Shasthya Kendra (DSK)',
      'email': 'psea@dskbangladesh.org'
    },
    // {
    //   'num': '01901310200',
    //   'org': 'Addiction Management and Integrated Care',
    //   'email': 'safeguarding_committee@amic.org.bd'
    // },
    {
      'num': '01716896162',
      'org': 'Village Education Resource Center (VERC)',
      'email': 'vercpsea@vercbd.org'
    },
    {
      'num': '01763568402',
      'org': 'Rupantar',
      'email': 'ananna@rupantar.org'
    },
    {
      'num': '01713149304',
      'org': 'Eco-Social Development Organization (ESDO)',
      'email': 'esdo.safeguarding2021@gmail.com'
    },
    {
      'num': '01777771515',
      'org': 'Sajida Foundation',
      'email': 'shec@sajidafoundation.org'
    },
    {
      'num': '01711965593',
      'org': 'Nabolok',
      'email': 'setunabolok@gmail.com'
    },
    {
      'num': '01717305141',
      'org': 'Bhumijo',
      'email': 'farhana.r@bhumijo.com'
    },
    {
      'num': '01713484599',
      'org': 'SKS Foundation',
      'email': 'ummequlsumila@sks-bd.org'
    },
    {
      'num': '01730044916',
      'org': 'BASA Foundation',
      'email': 'sabrina.basa.safeguard@gmail.com'
    },
  ];

  final List<bool> _expandedImportant = [];
  bool _expandedSafeguarding = false; // track safeguarding expand state

  @override
  void initState() {
    super.initState();
    _expandedImportant.addAll(List.filled(importantNumbers.length, false));
  }

  void _launchDialer(String number) async {
    final url = Uri.parse('tel:$number');
    if (await canLaunchUrl(url)) {
      await launchUrl(url);
    }
  }

  void _launchEmail(String email) async {
    if (email.isEmpty) return;
    final url = Uri.parse('mailto:$email');
    if (await canLaunchUrl(url)) {
      await launchUrl(url);
    }
  }

  void _showLoginPopup() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Login required"),
        content: const Text(
            "You must be logged in to view the Safeguarding Focal(s) information."),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.pushNamed(context, "/login"); // go to login page
            },
            child: const Text("Login"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.deepPurple,
      appBar: AppBar(
        title: const Text(
          'Important Numbers',
          style: TextStyle(color: Colors.white),
        ),
        backgroundColor: Colors.deepPurple,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'National Helpline Numbers',
              style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: Colors.white),
            ),
            const SizedBox(height: 12),
            ListView.separated(
              physics: const NeverScrollableScrollPhysics(),
              shrinkWrap: true,
              itemCount: importantNumbers.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (_, i) {
                final item = importantNumbers[i];
                return Card(
                  color: Colors.primaries[i % Colors.primaries.length][200],
                  child: Column(
                    children: [
                      ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                            vertical: 12, horizontal: 16),
                        leading: IconButton(
                          icon: const Icon(Icons.phone,
                              size: 36, color: Colors.white),
                          onPressed: () => _launchDialer(item['num'] ?? ''),
                        ),
                        title: Text(item['num'] ?? '',
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 20)),
                        subtitle: Text(item['title'] ?? '',
                            style: const TextStyle(fontSize: 16)),
                        trailing: IconButton(
                          icon: Icon(
                            _expandedImportant[i]
                                ? Icons.arrow_drop_up
                                : Icons.arrow_drop_down,
                            color: Colors.white,
                            size: 36,
                          ),
                          onPressed: () {
                            setState(() {
                              _expandedImportant[i] = !_expandedImportant[i];
                            });
                          },
                        ),
                      ),
                      if (_expandedImportant[i])
                        Padding(
                          padding: const EdgeInsets.only(
                              left: 16, right: 16, bottom: 12),
                          child: Text(item['desc'] ?? '',
                              style: const TextStyle(fontSize: 14)),
                        ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: 24),

            // Safeguarding section
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text(
                'Safeguarding Focal(s)',
                style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Colors.white),
              ),
              trailing: IconButton(
                icon: Icon(
                  _expandedSafeguarding
                      ? Icons.arrow_drop_up
                      : Icons.arrow_drop_down,
                  size: 36,
                  color: Colors.white,
                ),
                onPressed: () {
                  final user = FirebaseAuth.instance.currentUser;
                  if (user == null) {
                    _showLoginPopup();
                  } else {
                    setState(() {
                      _expandedSafeguarding = !_expandedSafeguarding;
                    });
                  }
                },
              ),
            ),
            if (_expandedSafeguarding)
              Column(
                children: safeguardingNumbers.map((item) {
                  int index = safeguardingNumbers.indexOf(item);
                  return Card(
                    color: Colors.primaries[index % Colors.primaries.length]
                    [300],
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                              vertical: 12, horizontal: 16),
                          leading: IconButton(
                            icon: const Icon(Icons.phone,
                                size: 36, color: Colors.white),
                            onPressed: () =>
                                _launchDialer(item['num'] ?? ''),
                          ),
                          title: Text(item['num'] ?? '',
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold, fontSize: 20)),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(item['org'] ?? '',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w500)),
                              if ((item['email'] ?? '').isNotEmpty)
                                Padding(
                                  padding: const EdgeInsets.only(top: 8.0),
                                  child: Row(
                                    crossAxisAlignment:
                                    CrossAxisAlignment.center,
                                    children: [
                                      IconButton(
                                        padding: EdgeInsets.zero,
                                        constraints: const BoxConstraints(),
                                        icon: const Icon(Icons.email,
                                            size: 24, color: Colors.white),
                                        onPressed: () => _launchEmail(
                                            item['email'] ?? ''),
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: GestureDetector(
                                          onTap: () => _launchEmail(
                                              item['email'] ?? ''),
                                          child: Text(
                                            item['email'] ?? '',
                                            style: const TextStyle(
                                                color: Colors.white,
                                                decoration:
                                                TextDecoration.underline),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
          ],
        ),
      ),
    );
  }
}
