import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'super_admin_dashboard.dart';

class ManageTopicsScreen extends StatefulWidget {
  @override
  _ManageTopicsScreenState createState() => _ManageTopicsScreenState();
}

class _ManageTopicsScreenState extends State<ManageTopicsScreen> {
  final _topicController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Manage Knowledge Topics"),
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
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: TextField(
              controller: _topicController,
              decoration: InputDecoration(
                labelText: "New Topic Name",
                border: OutlineInputBorder(),
              ),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              if (_topicController.text.trim().isNotEmpty) {
                await FirebaseFirestore.instance.collection('topics').add({
                  'title': _topicController.text.trim(),
                  'createdAt': DateTime.now(),
                });
                _topicController.clear();
              }
            },
            child: Text("Add Topic"),
          ),
          Expanded(
            child: StreamBuilder(
              stream: FirebaseFirestore.instance
                  .collection('topics')
                  .orderBy('createdAt', descending: true)
                  .snapshots(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) return Center(child: CircularProgressIndicator());
                var topics = snapshot.data!.docs;
                return ListView.builder(
                  itemCount: topics.length,
                  itemBuilder: (context, index) {
                    return ListTile(
                      title: Text(topics[index]['title']),
                      trailing: IconButton(
                        icon: Icon(Icons.delete, color: Colors.red),
                        onPressed: () async {
                          await FirebaseFirestore.instance
                              .collection('topics')
                              .doc(topics[index].id)
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
