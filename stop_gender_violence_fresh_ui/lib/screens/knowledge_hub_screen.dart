import 'package:flutter/material.dart';
import 'knowledge_detail_screen.dart';

class KnowledgeHubScreen extends StatelessWidget {
  KnowledgeHubScreen({Key? key}) : super(key: key);

  final List<Map<String, String>> knowledgeItems = [
    {
      'id': '1',
      'title': 'What is Safeguarding?',
      'description': 'Learn about safeguarding, rights and protection measures.',
      'image': 'assets/k1.png',
    },
    {
      'id': '2',
      'title': 'What is Gender-Based Violence?',
      'description': 'Understand different forms of gender-based violence.',
      'image': 'assets/k2.jpg',
    },
    // {
    //   'id': '3',
    //   'title': 'Types of Gender Based Violence',
    //   'description': 'Know how to identify different forms of Gender Based Violence.',
    //   'image': 'assets/k3.jpg',
    // },
    {
      'id': '4',
      'title': 'Roles & Responsibilities in Safeguarding',
      'description': 'Shows how safeguarding is a shared responsibility.',
      'image': 'assets/k4.png',
    },
    // {
    //   'id': '5',
    //   'title': 'Reporting Mechanisms',
    //   'description': 'Encourages action and ensures reports are detailed and helpful.',
    //   'image': 'assets/safe.png',
    // },
    {
      'id': '6',
      'title': 'Prevention of Gender Based Violence',
      'description': 'Preventive measures to stop Gender Based Violence',
      'image': 'assets/k5.png',
    },
    {
      'id': '7',
      'title': 'Myths vs. Facts about Gender Based Violence',
      'description': 'Encourages action and ensures reports are detailed and helpful.',
      'image': 'assets/k6.png',
    },
    // {
    //   'id': '8',
    //   'title': 'Safeguarding Principles',
    //   'description': 'Core principles of Safeguarding',
    //   'image': 'assets/safe.png',
    // },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFA81E24), // Page background red
      appBar: AppBar(
        backgroundColor: const Color(0xFFA81E24),
        elevation: 0,
        title: const Text("Knowledge Hub"),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // Top banner image
            Image.asset(
              'assets/header.jpg', // <- as you wanted red header image
              width: double.infinity,
              height: 350,
              fit: BoxFit.cover,
              errorBuilder: (context, error, stackTrace) {
                return const SizedBox(height: 160);
              },
            ),

            const SizedBox(height: 16),

            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Column(
                children: knowledgeItems.map((item) {
                  return Card(
                    color: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    margin: const EdgeInsets.only(bottom: 16),
                    child: Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: Row(
                        children: [
                          // Image left
                          ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: SizedBox(
                              width: 200,
                              height: 120,
                              child: Image.asset(
                                item['image']!,
                                fit: BoxFit.cover,
                                errorBuilder: (context, error, stackTrace) {
                                  return Container(
                                    color: Colors.grey[300],
                                    child: const Icon(Icons.image, size: 40),
                                  );
                                },
                              ),
                            ),
                          ),

                          const SizedBox(width: 12),

                          // Right side
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item['title']!,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.black87,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  item['description']!,
                                  style: const TextStyle(
                                    fontSize: 13,
                                    color: Colors.black54,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: ElevatedButton(
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor:
                                      const Color(0xFFA81E24),
                                      foregroundColor: Colors.white,
                                    ),
                                    onPressed: () {
                                      Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) =>
                                              KnowledgeDetailScreen(
                                                topicId: item['id']!,
                                                title: item['title']!,
                                              ),
                                        ),
                                      );
                                    },
                                    child: const Text("Read More"),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
