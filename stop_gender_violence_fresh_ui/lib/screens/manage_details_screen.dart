import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'super_admin_dashboard.dart';

class ManageDetailsScreen extends StatefulWidget {
  @override
  _ManageDetailsScreenState createState() => _ManageDetailsScreenState();
}

class _ManageDetailsScreenState extends State<ManageDetailsScreen> {
  final _detailController = TextEditingController();
  String _selectedType = "Text";
  final List<String> _types = ["Text", "PDF", "Image", "Video", "Link"];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Manage Knowledge Details"),
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
      body: Column(
        children: [
          DropdownButton<String>(
            value: _selectedType,
            onChanged: (val) => setState(() => _selectedType = val!),
            items: _types.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
          ),
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: TextField(
              controller: _detailController,
              decoration: InputDecoration(
                labelText: "Enter ${_selectedType} detail (URL or text)",
                border: OutlineInputBorder(),
              ),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              if (_detailController.text.trim().isNotEmpty) {
                await FirebaseFirestore.instance.collection('details').add({
                  'type': _selectedType,
                  'content': _detailController.text.trim(),
                  'createdAt': DateTime.now(),
                });
                _detailController.clear();
              }
            },
            child: Text("Add Detail"),
          ),
          Expanded(
            child: StreamBuilder(
              stream: FirebaseFirestore.instance
                  .collection('details')
                  .orderBy('createdAt', descending: true)
                  .snapshots(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) return Center(child: CircularProgressIndicator());
                var details = snapshot.data!.docs;
                return ListView.builder(
                  itemCount: details.length,
                  itemBuilder: (context, index) {
                    return ListTile(
                      title: Text("${details[index]['type']}: ${details[index]['content']}"),
                      trailing: IconButton(
                        icon: Icon(Icons.delete, color: Colors.red),
                        onPressed: () async {
                          await FirebaseFirestore.instance
                              .collection('details')
                              .doc(details[index].id)
                              .delete();
                        },
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
