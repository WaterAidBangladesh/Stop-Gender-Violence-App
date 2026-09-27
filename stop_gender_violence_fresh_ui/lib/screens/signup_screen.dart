import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'home_page.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({Key? key}) : super(key: key);

  @override
  _SignupScreenState createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passController = TextEditingController();
  final _confirmPassController = TextEditingController();

  bool _obscurePass = true;
  bool _obscureConfirmPass = true;
  bool _isLoading = false;
  bool _emailSent = false;

  Future<void> _signupUser() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final email = _emailController.text.trim();
      final phone = _phoneController.text.trim();
      final password = _passController.text.trim();
      final name = _nameController.text.trim();

      // Create user in Firebase Auth
      UserCredential userCredential = await FirebaseAuth.instance
          .createUserWithEmailAndPassword(email: email, password: password);

      final uid = userCredential.user!.uid;

      // Save user details in Firestore
      await FirebaseFirestore.instance.collection('users').doc(uid).set({
        'uid': uid,
        'name': name,
        'email': email,
        'phone': phone.isNotEmpty ? phone : null,
        'createdAt': DateTime.now(),
      });

      // Send email verification
      await userCredential.user!.sendEmailVerification();
      setState(() => _emailSent = true);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Verification email sent! Check your inbox or spam."),
        ),
      );
    } on FirebaseAuthException catch (e) {
      String errorMessage = 'Signup failed';
      if (e.code == 'email-already-in-use') {
        errorMessage = 'This email is already registered';
      } else if (e.code == 'weak-password') {
        errorMessage = 'Password is too weak';
      } else if (e.code == 'invalid-email') {
        errorMessage = 'Invalid email address';
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(errorMessage)),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error: $e")),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _checkEmailVerified() async {
    User? user = FirebaseAuth.instance.currentUser;
    await user?.reload();
    if (user != null && user.emailVerified) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const HomePage()),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Email not verified yet!")),
      );
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passController.dispose();
    _confirmPassController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF2D2A4A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF3F51B5),
        elevation: 0,
        title: const Text(
          "Sign Up",
          style: TextStyle(color: Colors.white),
        ),
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          IconButton(
            icon: const Icon(Icons.home, color: Colors.white),
            onPressed: () {
              Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (context) => const HomePage()),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            Image.asset(
              'assets/signup.jpg',
              width: double.infinity,
              height: 450,
              fit: BoxFit.cover,
            ),
            Container(
              color: const Color(0xFF3F51B5),
              padding: const EdgeInsets.all(20),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          'Already have an account?',
                          style: TextStyle(color: Colors.white),
                        ),
                        const SizedBox(width: 4),
                        GestureDetector(
                          onTap: () {
                            Navigator.pushReplacementNamed(context, '/login');
                          },
                          child: const Text(
                            'Log in',
                            style: TextStyle(
                              color: Colors.white,
                              decoration: TextDecoration.underline,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Create an account',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 20),
                    _buildTextField(_nameController, 'Name', Icons.person),
                    const SizedBox(height: 12),
                    _buildTextField(
                        _emailController, 'Email', Icons.email,
                        keyboardType: TextInputType.emailAddress),
                    const SizedBox(height: 12),
                    _buildTextField(
                        _phoneController, 'Phone number', Icons.phone,
                        keyboardType: TextInputType.phone),
                    const SizedBox(height: 12),
                    _buildPasswordField(
                        _passController, 'Password', Icons.key, _obscurePass,
                            () => setState(() => _obscurePass = !_obscurePass)),
                    const SizedBox(height: 12),
                    _buildPasswordField(_confirmPassController,
                        'Confirm password', Icons.lock, _obscureConfirmPass,
                            () => setState(() =>
                        _obscureConfirmPass = !_obscureConfirmPass)),
                    const SizedBox(height: 20),

                    Align(
                      alignment: Alignment.centerRight,
                      child: GestureDetector(
                        onTap: _isLoading ? null : _signupUser,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (_isLoading)
                              const CircularProgressIndicator(color: Colors.white)
                            else
                              const Text(
                                'Sign up',
                                style: TextStyle(
                                  fontSize: 18,
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            const SizedBox(width: 10),
                            const CircleAvatar(
                              radius: 28,
                              backgroundColor: Colors.white,
                              child: Icon(
                                Icons.arrow_forward,
                                color: Color(0xFF3F51B5),
                                size: 28,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Email verification button
                    if (_emailSent)
                      ElevatedButton(
                        onPressed: _checkEmailVerified,
                        style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green),
                        child: const Text("I have verified my email"),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String hint,
      IconData icon,
      {TextInputType keyboardType = TextInputType.text}) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      validator: (value) {
        if (value == null || value.trim().isEmpty) {
          return '$hint is required';
        }
        if (hint == 'Email') {
          final emailRegex =
          RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
          if (!emailRegex.hasMatch(value)) return 'Enter a valid email';
        }
        return null;
      },
      decoration: InputDecoration(
        prefixIcon: Icon(icon, color: Colors.white),
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white70),
        enabledBorder:
        const UnderlineInputBorder(borderSide: BorderSide(color: Colors.white54)),
        focusedBorder:
        const UnderlineInputBorder(borderSide: BorderSide(color: Colors.white)),
      ),
    );
  }

  Widget _buildPasswordField(TextEditingController controller, String hint,
      IconData icon, bool obscureText, VoidCallback toggle) {
    return TextFormField(
      controller: controller,
      obscureText: obscureText,
      style: const TextStyle(color: Colors.white),
      validator: (value) {
        if (value == null || value.isEmpty) {
          return '$hint is required';
        }
        if (hint == 'Password' && value.length < 6) {
          return 'Password must be at least 6 characters';
        }
        if (hint == 'Confirm password' && value != _passController.text) {
          return 'Passwords do not match';
        }
        return null;
      },
      decoration: InputDecoration(
        prefixIcon: Icon(icon, color: Colors.white),
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white70),
        suffixIcon: IconButton(
          icon: Icon(obscureText ? Icons.visibility_off : Icons.visibility,
              color: Colors.white),
          onPressed: toggle,
        ),
        enabledBorder:
        const UnderlineInputBorder(borderSide: BorderSide(color: Colors.white54)),
        focusedBorder:
        const UnderlineInputBorder(borderSide: BorderSide(color: Colors.white)),
      ),
    );
  }
}
