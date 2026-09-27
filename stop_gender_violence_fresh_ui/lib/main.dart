import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';

import 'utils/app_colors.dart';
import 'utils/navigation.dart';
import 'screens/splash_screen.dart';
import 'screens/home_page.dart';
import 'screens/knowledge_hub_screen.dart';
import 'screens/knowledge_detail_screen.dart';
import 'screens/report_intro_screen.dart';
import 'screens/report_form_screen.dart';
import 'screens/login_screen.dart';
import 'screens/signup_screen.dart';
import 'screens/emergency_contacts_screen.dart';
import 'screens/admin_panel_screen.dart';
import 'screens/menu_screen.dart';
import 'screens/contact_us.dart'; // ⬅️ Added Contact Us
import 'bharosha/chat_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(); // ✅ No firebase_options.dart needed
  runApp(StopGenderViolenceApp());
}

class StopGenderViolenceApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Stop Gender Violence - UI Demo',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primaryColor: AppColors.primary,
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: AppBarTheme(color: AppColors.primary),
      ),
      home: const SplashScreen(),
      onGenerateRoute: (settings) {
        Widget page;

        switch (settings.name) {
          case '/home':
            page = const HomePage();
            break;

          case '/knowledge':
            page = KnowledgeHubScreen();
            break;

          case '/knowledgeDetail':
            final args = settings.arguments as Map<String, dynamic>?;

            final topicId = args?['topicId'] ?? "0";
            final title = args?['title'] ?? "Knowledge";

            page = KnowledgeDetailScreen(
              topicId: topicId,
              title: title,
            );
            break;

          case '/reportIntro':
            page = ReportIntroScreen();
            break;

          case '/reportForm':
            page = ReportFormScreen();
            break;

          case '/login':
            page = LoginScreen();
            break;

          case '/signup':
            page = SignupScreen();
            break;

          case '/emergency':
            page = EmergencyContactsScreen();
            break;

          case '/admin':
            page = AdminPanelScreen();
            break;

          case '/menu':
            page = MenuScreen();
            break;

          case '/contact': // ⬅️ NEW Contact Us Page
            page = ContactUsPage();
            break;

          case '/bharosha': // Bharosha — safeguarding guidance, no login needed
            page = const BharoshaChatScreen();
            break;

          default:
            page = const SplashScreen();
        }

        return createAnimatedRoute(page, settings);
      },
    );
  }
}
