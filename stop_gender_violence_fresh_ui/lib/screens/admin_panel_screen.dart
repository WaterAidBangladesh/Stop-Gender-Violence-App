import 'package:flutter/material.dart';

class AdminPanelScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    // Local-only demo admin panel (no backend)
    final demoReports = List.generate(6, (i) => {
      'name': i % 2 == 0 ? 'Anonymous' : 'User ${i+1}',
      'type': ['Physical','Sexual','Emotional','Harassment'][i % 4],
      'date': '2025-08-0${i+1}',
      'time': '12:3${i} PM',
      'description': 'This is a short demo description of the incident #${i+1}.'
    });

    return Scaffold(
      appBar: AppBar(title: Text('Admin Panel (Demo)')),
      body: ListView.separated(
        padding: EdgeInsets.all(12),
        itemCount: demoReports.length,
        separatorBuilder: (_,__) => Divider(),
        itemBuilder: (_,i) {
          final r = demoReports[i];
          return ListTile(
            title: Text(r['name']!),
            subtitle: Text('${r['type']} • ${r['date']} ${r['time']}\n${r['description']}'),
            isThreeLine: true,
            trailing: PopupMenuButton<String>(
              onSelected: (v) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Action: $v (placeholder)'))),
              itemBuilder: (_) => [PopupMenuItem(value: 'delete', child: Text('Delete'))],
            ),
            onTap: () => showDialog(context: context, builder: (_) => AlertDialog(title: Text('Report Details'), content: Text(r['description']!), actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: Text('Close'))])),
          );
        },
      ),
    );
  }
}
