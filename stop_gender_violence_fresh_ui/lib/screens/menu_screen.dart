import 'package:flutter/material.dart';

class MenuScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Menu')),
      body: ListView(padding: EdgeInsets.all(12), children: [
        ListTile(leading: Icon(Icons.person), title: Text('Profile (placeholder)'), onTap: () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Profile (placeholder)')))),
        ListTile(leading: Icon(Icons.info), title: Text('About'), onTap: () => showAboutDialog(context: context, applicationName: 'Stop Gender Violence (Demo)', applicationVersion: '0.1')),
      ]),
    );
  }
}
