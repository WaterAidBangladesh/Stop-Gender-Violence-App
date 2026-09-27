// knowledge_data.dart
import 'package:flutter/material.dart';

/// Data model for a knowledge topic
class KnowledgeTopic {
  final String id;             // Unique topic id
  final String title;          // Title of the topic
  final String description;    // Short description
  final String? imageUrl;      // Banner image
  final String? pdfPath;       // PDF file path (local or Firebase)
  final List<String>? videoUrls; // YouTube links
  final String? highlight;     // Key highlight text
  final String? imagePlaceholder; // Related image

  KnowledgeTopic({
    required this.id,
    required this.title,
    required this.description,
    this.imageUrl,
    this.pdfPath,
    this.videoUrls,
    this.highlight,
    this.imagePlaceholder,
  });
}

/// Dummy data list (replace later with Firebase fetch)
List<KnowledgeTopic> topics = [
  KnowledgeTopic(
    id: "1",
    title: "Safeguarding Basics",
    description: "Learn about safeguarding, rights and protection measures.",
    imageUrl: "assets/safe.png",
    pdfPath: "assets/safeguardingpdf.pdf",
    videoUrls: [
      "https://www.youtube.com/watch?v=VIDEO_ID_1",
      "https://www.youtube.com/watch?v=VIDEO_ID_2",
    ],
    highlight: "Protecting people from harm, abuse, neglect, and exploitation.",
    imagePlaceholder: "assets/safe2.png",
  ),
  KnowledgeTopic(
    id: "2",
    title: "Child Protection",
    description: "Understanding child safety, rights, and reporting systems.",
    imageUrl: "assets/child.png",
    pdfPath: "assets/child_protection.pdf",
    videoUrls: [
      "https://www.youtube.com/watch?v=VIDEO_ID_3",
    ],
    highlight: "Every child has the right to grow in a safe environment.",
    imagePlaceholder: "assets/child2.png",
  ),
  KnowledgeTopic(
    id: "3",
    title: "Gender Equality",
    description: "Promoting equality, preventing discrimination and harassment.",
    imageUrl: "assets/gender.png",
    pdfPath: "assets/gender_equality.pdf",
    videoUrls: [
      "https://www.youtube.com/watch?v=VIDEO_ID_4",
    ],
    highlight: "Equality for all genders in work and community spaces.",
    imagePlaceholder: "assets/gender2.png",
  ),
];
