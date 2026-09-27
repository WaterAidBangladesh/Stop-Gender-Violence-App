import 'package:flutter/material.dart';

class ReportIntroScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Report an Incident')),
      body: Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('Do you want to create an account to track your report?', textAlign: TextAlign.center),
            SizedBox(height: 18),
            ElevatedButton(onPressed: () => Navigator.of(context).pushNamed('/signup'), child: Text('Yes, sign up')),
            SizedBox(height: 12),
            ElevatedButton(onPressed: () => Navigator.of(context).pushNamed('/reportForm'), child: Text('No, report anonymously')),
          ]),
        ),
      ),
    );
  }
}
