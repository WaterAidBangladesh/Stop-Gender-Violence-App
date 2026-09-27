// verify_email_screen.dart
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'home_page.dart';

class VerifyEmailScreen extends StatefulWidget {
  final User user;

  const VerifyEmailScreen({required this.user, Key? key}) : super(key: key);

  @override
  _VerifyEmailScreenState createState() => _VerifyEmailScreenState();
}

class _VerifyEmailScreenState extends State<VerifyEmailScreen> {
  bool _isVerified = false;
  bool _isLoading = false;

  Future<void> _checkVerification() async {
    setState(() => _isLoading = true);
    await widget.user.reload();
    final user = FirebaseAuth.instance.currentUser!;
    if (user.emailVerified) {
      setState(() => _isVerified = true);
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const HomePage()),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Email not verified yet')),
      );
    }
    setState(() => _isLoading = false);
  }

  Future<void> _resendEmail() async {
    try {
      await widget.user.sendEmailVerification();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Verification email sent again')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Verify Email')),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              'A verification email has been sent to your email. Please verify before proceeding.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _isLoading ? null : _checkVerification,
              child: _isLoading
                  ? const CircularProgressIndicator()
                  : const Text('I have verified'),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: _resendEmail,
              child: const Text('Resend Email'),
            ),
          ],
        ),
      ),
    );
  }
}
