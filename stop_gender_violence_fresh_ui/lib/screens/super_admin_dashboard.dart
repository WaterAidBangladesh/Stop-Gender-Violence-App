import 'package:flutter/material.dart';
import 'manage_topics_screen.dart';
import 'manage_details_screen.dart';
import 'view_reports_screen.dart';

class SuperAdminDashboard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Super Admin Dashboard"),
        backgroundColor: Colors.redAccent,
      ),
      body: ListView(
        children: [
          ListTile(
            leading: Icon(Icons.library_books),
            title: Text("Manage Knowledge Topics"),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => ManageTopicsScreen()),
            ),
          ),
          ListTile(
            leading: Icon(Icons.edit_document),
            title: Text("Manage Knowledge Details"),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => ManageDetailsScreen()),
            ),
          ),
          ListTile(
            leading: Icon(Icons.report),
            title: Text("View Submitted Reports"),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => ViewReportsScreen()),
            ),
          ),
        ],
      ),
    );
  }
}
