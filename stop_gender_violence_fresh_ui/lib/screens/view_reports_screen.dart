import 'package:flutter/material.dart';
import 'super_admin_dashboard.dart';

class ViewReportsScreen extends StatelessWidget {
  final List<String> reports = [
    "Report 1: Harassment in workplace",
    "Report 2: Misuse of resources",
    "Report 3: Abuse complaint"
  ]; // later fetch from Firebase

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Submitted Reports"),
        actions: [
          IconButton(
            icon: Icon(Icons.home),
            onPressed: () {
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (context) => SuperAdminDashboard()),
                    (route) => false,
              );
            },
          ),
        ],
      ),
      body: ListView.builder(
        itemCount: reports.length,
        itemBuilder: (context, index) {
          return ListTile(
            leading: Icon(Icons.report, color: Colors.red),
            title: Text(reports[index]),
          );
        },
      ),
    );
  }
}
