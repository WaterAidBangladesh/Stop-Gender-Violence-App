import 'package:flutter/material.dart';

Route createAnimatedRoute(Widget page, RouteSettings settings) {
  return PageRouteBuilder(
    settings: settings,
    transitionDuration: Duration(milliseconds: 420),
    pageBuilder: (context, animation, secondaryAnimation) => page,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      // Fade + slide from right
      final offsetAnimation = Tween<Offset>(begin: Offset(0.15, 0), end: Offset.zero).animate(CurvedAnimation(parent: animation, curve: Curves.easeOut));
      final fade = Tween<double>(begin: 0.0, end: 1.0).animate(CurvedAnimation(parent: animation, curve: Curves.easeOut));
      return SlideTransition(position: offsetAnimation, child: FadeTransition(opacity: fade, child: child));
    },
  );
}
