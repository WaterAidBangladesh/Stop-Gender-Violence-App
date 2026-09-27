import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../utils/app_colors.dart';
import 'contact_us.dart';

class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final PageController _pageController = PageController(viewportFraction: 0.7);
  int _currentPage = 0;
  bool _isLoggedIn = false;
  User? _currentUser;

  @override
  void initState() {
    super.initState();
    _checkLoginStatus();
  }

  void _checkLoginStatus() {
    final user = FirebaseAuth.instance.currentUser;
    if (user != null) {
      setState(() {
        _isLoggedIn = true;
        _currentUser = user;
      });
    }
  }

  Future<void> _logout() async {
    await FirebaseAuth.instance.signOut();
    setState(() {
      _isLoggedIn = false;
      _currentUser = null;
    });
    Navigator.pop(context);
  }

  void _showProfilePopup() {
    final user = _currentUser;
    String displayName = "";

    if (user != null) {
      if (user.displayName != null && user.displayName!.isNotEmpty) {
        displayName = user.displayName!;
      } else if (user.email != null) {
        final namePart = user.email!.split('@').first;
        displayName = namePart.replaceAll('.', ' ').split(' ').map((word) {
          if (word.isEmpty) return '';
          return word[0].toUpperCase() + word.substring(1);
        }).join(' ');
      } else {
        displayName = "User";
      }
    }

    showDialog(
      context: context,
      barrierDismissible: true,
      barrierColor: Colors.black.withOpacity(0.4),
      builder: (BuildContext context) {
        return Center(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 6, sigmaY: 6),
              child: Material(
                color: Colors.white.withOpacity(0.95),
                elevation: 12,
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  width: 280,
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.person, size: 50, color: Colors.purple),
                      const SizedBox(height: 10),
                      Text(
                        displayName,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: Colors.black87,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        user?.email ?? '',
                        style: const TextStyle(
                          color: Colors.black54,
                          fontSize: 14,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      const Divider(),
                      const SizedBox(height: 8),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.red,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          minimumSize: const Size(double.infinity, 40),
                        ),
                        onPressed: _logout,
                        icon: const Icon(Icons.logout, color: Colors.white),
                        label: const Text(
                          "Logout",
                          style: TextStyle(color: Colors.white),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  void _showPosterPopup() {
    int currentImage = 0;
    final images = ['assets/1.png', 'assets/2.png'];

    showDialog(
      context: context,
      barrierDismissible: true,
      barrierColor: Colors.black.withOpacity(0.6),
      builder: (BuildContext context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return Center(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      Image.asset(
                        images[currentImage],
                        width: MediaQuery.of(context).size.width * 0.9,
                        fit: BoxFit.contain,
                      ),
                      Positioned(
                        right: 16,
                        child: IconButton(
                          icon: const Icon(Icons.arrow_forward_ios,
                              color: Colors.white, size: 32),
                          onPressed: () {
                            setState(() {
                              currentImage =
                                  (currentImage + 1) % images.length;
                            });
                          },
                        ),
                      ),
                      Positioned(
                        top: 16,
                        right: 16,
                        child: IconButton(
                          icon: const Icon(Icons.close,
                              color: Colors.white, size: 28),
                          onPressed: () => Navigator.pop(context),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final int totalCards = _isLoggedIn ? 6 : 5;

    return Scaffold(
      backgroundColor: const Color(0xFF5E2A8E),
      appBar: AppBar(
        backgroundColor: const Color(0xFF5E2A8E),
        elevation: 0,
        leading: Builder(
          builder: (context) => IconButton(
            icon: const Icon(Icons.menu, color: Colors.white),
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
        ),
        actions: [
          _isLoggedIn
              ? IconButton(
            icon: const CircleAvatar(
              backgroundColor: Colors.white,
              child: Icon(Icons.person, color: Colors.purple),
            ),
            onPressed: _showProfilePopup,
          )
              : TextButton(
            onPressed: () => Navigator.pushNamed(context, '/login'),
            child: const Text("Login",
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: Color(0xFF5E2A8E)),
              child: Text(
                'Menu',
                style: TextStyle(color: Colors.white, fontSize: 24),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.chat_bubble_outline, color: Color(0xFF5E2A8E)),
              title: const Text("Ask Bharosha"),
              subtitle: const Text("ভরসা — safeguarding guidance"),
              onTap: () {
                Navigator.pop(context);
                Navigator.pushNamed(context, '/bharosha');
              },
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.book),
              title: const Text("Knowledge Hub"),
              onTap: () => Navigator.pushNamed(context, '/knowledge'),
            ),
            ListTile(
              leading: const Icon(Icons.phone),
              title: const Text("Important numbers"),
              onTap: () {
                Navigator.pop(context);
                Navigator.pushNamed(context, '/emergency');
              },
            ),
            ListTile(
              leading: const Icon(Icons.contact_mail),
              title: const Text('Contact Us'),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => ContactUsPage()),
                );
              },
            ),
          ],
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Image.asset('assets/header4.jpg',
                fit: BoxFit.cover, width: double.infinity),

            // Bharosha, above the Knowledge Hub on purpose: someone who needs
            // help should not have to scroll past reading material to find it.
            // No login required, and the emergency referrals inside it work
            // offline.
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: () => Navigator.pushNamed(context, '/bharosha'),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Row(
                      children: [
                        Container(
                          width: 46,
                          height: 46,
                          decoration: BoxDecoration(
                            color: const Color(0xFF5E2A8E).withOpacity(0.10),
                            borderRadius: BorderRadius.circular(23),
                          ),
                          child: const Icon(Icons.chat_bubble_outline,
                              color: Color(0xFF5E2A8E)),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Ask Bharosha · ভরসা',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  color: Color(0xFF2D2A4A),
                                ),
                              ),
                              SizedBox(height: 2),
                              Text(
                                'Questions about safeguarding or violence, in Bangla or English. '
                                'No account needed.',
                                style: TextStyle(fontSize: 12, color: Colors.black54),
                              ),
                            ],
                          ),
                        ),
                        const Icon(Icons.arrow_forward_ios,
                            size: 16, color: Colors.black38),
                      ],
                    ),
                  ),
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Knowledge Hub',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 180,
                    child: Stack(
                      children: [
                        PageView.builder(
                          controller: _pageController,
                          itemCount: totalCards,
                          onPageChanged: (index) {
                            setState(() => _currentPage = index);
                          },
                          itemBuilder: (context, index) {
                            return AnimatedBuilder(
                              animation: _pageController,
                              builder: (context, child) {
                                double value = 1.0;
                                if (_pageController.position.haveDimensions) {
                                  value = (_pageController.page! - index).abs();
                                  value = (1 - (value * 0.3)).clamp(0.0, 1.0);
                                }

                                // Poster card for logged-in users only
                                if (_isLoggedIn && index == 5) {
                                  return Center(
                                    child: GestureDetector(
                                      onTap: _showPosterPopup,
                                      child: Container(
                                        margin: const EdgeInsets.symmetric(
                                            horizontal: 8),
                                        child: ClipRRect(
                                          borderRadius:
                                          BorderRadius.circular(8),
                                          child: Image.asset(
                                            'assets/poster.jpg',
                                            fit: BoxFit.cover,
                                            width: double.infinity,
                                            height: 180,
                                          ),
                                        ),
                                      ),
                                    ),
                                  );
                                }

                                return Center(
                                  child: Container(
                                    margin: const EdgeInsets.symmetric(
                                        horizontal: 8),
                                    child: GestureDetector(
                                      onTap: () {
                                        if (index == 0) {
                                          Navigator.pushNamed(
                                            context,
                                            '/knowledgeDetail',
                                            arguments: {
                                              'title': 'What is Safeguarding?',
                                              'topicId': '1',
                                            },
                                          );
                                        } else if (index == 1) {
                                          Navigator.pushNamed(
                                            context,
                                            '/knowledgeDetail',
                                            arguments: {
                                              'title':
                                              'What is Gender-Based Violence?',
                                              'topicId': '2',
                                            },
                                          );
                                        } else if (index == 2) {
                                          Navigator.pushNamed(
                                            context,
                                            '/knowledgeDetail',
                                            arguments: {
                                              'title':
                                              'Roles & Responsibilities in Safeguarding',
                                              'topicId': '4',
                                            },
                                          );
                                        } else if (index == 3) {
                                          Navigator.pushNamed(
                                            context,
                                            '/knowledgeDetail',
                                            arguments: {
                                              'title':
                                              'Prevention of Gender Based Violence',
                                              'topicId': '6',
                                            },
                                          );
                                        } else {
                                          Navigator.pushNamed(
                                            context,
                                            '/knowledgeDetail',
                                            arguments: {
                                              'title':
                                              'Myths vs. Facts about Gender Based Violence',
                                              'topicId': '7',
                                            },
                                          );
                                        }
                                      },
                                      child: ClipRRect(
                                        borderRadius:
                                        BorderRadius.circular(8),
                                        child: Image.asset(
                                          'assets/knowledge${index + 1}.jpg',
                                          fit: BoxFit.cover,
                                          width: double.infinity,
                                          height: 180,
                                        ),
                                      ),
                                    ),
                                  ),
                                );
                              },
                            );
                          },
                        ),

                        // LEFT ARROW (hidden on first card)
                        if (_currentPage > 0)
                          Positioned(
                            left: 0,
                            top: 0,
                            bottom: 0,
                            child: IconButton(
                              icon: const Icon(Icons.arrow_back_ios,
                                  color: Colors.white),
                              onPressed: () {
                                _pageController.previousPage(
                                  duration:
                                  const Duration(milliseconds: 300),
                                  curve: Curves.easeInOut,
                                );
                              },
                            ),
                          ),

                        // RIGHT ARROW (hidden on last card)
                        if (_currentPage < totalCards - 1)
                          Positioned(
                            right: 0,
                            top: 0,
                            bottom: 0,
                            child: IconButton(
                              icon: const Icon(Icons.arrow_forward_ios,
                                  color: Colors.white),
                              onPressed: () {
                                _pageController.nextPage(
                                  duration:
                                  const Duration(milliseconds: 300),
                                  curve: Curves.easeInOut,
                                );
                              },
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: GestureDetector(
                      onTap: () =>
                          Navigator.pushNamed(context, '/knowledge'),
                      child: const Text(
                        'View all',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          decoration: TextDecoration.underline,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // Important numbers section (unchanged)
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    flex: 1,
                    child: Image.asset('assets/important.jpg',
                        fit: BoxFit.cover),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 1,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          'Important Numbers',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Colors.orange,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Access important helpline numbers available 24/7. Call these official numbers to get immediate support and guidance from established services.',
                          style: TextStyle(
                            color: Colors.grey[300],
                            fontSize: 12,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 12),
                        Stack(
                          alignment: Alignment.center,
                          children: [
                            Container(
                              width: 120,
                              height: 38,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius:
                                BorderRadius.circular(6),
                              ),
                            ),
                            GestureDetector(
                              onTap: () {
                                Navigator.pushNamed(context, '/emergency');
                              },
                              child: Container(
                                width: 120,
                                height: 38,
                                decoration: BoxDecoration(
                                  color: Colors.green,
                                  borderRadius:
                                  BorderRadius.circular(6),
                                ),
                                alignment: Alignment.center,
                                child: const Text(
                                  'View',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
