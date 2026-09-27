import 'package:flutter/material.dart';
import 'package:intl_phone_field/intl_phone_field.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';

class ReportFormScreen extends StatefulWidget {
  const ReportFormScreen({super.key});

  @override
  _ReportFormScreenState createState() => _ReportFormScreenState();
}

class _ReportFormScreenState extends State<ReportFormScreen> {
  final PageController _pc = PageController();
  int _idx = 0;

  final _dateCtl = TextEditingController();
  final _timeCtl = TextEditingController();
  final _descCtl = TextEditingController();

  String? _type;
  bool _consentToBeContacted = false;
  bool _confirmationChecked = false;
  String? _phoneNumber;

  File? _pickedFile;
  String? _uploadedFileUrl;
  bool _isUploading = false;

  String? _selectedDistrict;
  String? _selectedUpazila;

  final User? currentUser = FirebaseAuth.instance.currentUser;

  final Map<String, List<String>> districtUpazilaMap = {
    // (Include your full district-upazila map here, same as your original code)
  };

  final Map<String, String> incidentDescriptions = {
    'Sexual Exploitation':
    'Taking advantage of someone in a position of vulnerability or trust for sexual purposes or profit, including coercion or manipulation.',
    'Abuse':
    'Any action or neglect causing harm to a child or vulnerable adult. This includes physical, emotional, sexual abuse, neglect, or exploitation.',
    'Harassment':
    'Unwanted or offensive behaviour that violates a person’s dignity or creates an intimidating, hostile, or degrading environment. Can relate to characteristics like race, gender, age, disability, or other personal attributes.',
    'Human Trafficking':
    'The recruitment, transport, or exploitation of a person through force, coercion, or deception, often for labour, sexual exploitation, or other forms of abuse.',
  };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF7e2c76),
      appBar: AppBar(
        title: const Text('Report an Incident'),
        backgroundColor: const Color(0xFF7e2c76),
        elevation: 0,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.home, color: Colors.white),
            onPressed: () {
              Navigator.of(context).pushNamedAndRemoveUntil(
                '/home',
                    (Route<dynamic> route) => false,
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Image.asset(
            'assets/report.jpg',
            width: 250,
            height: 200,
            fit: BoxFit.cover,
          ),
          Expanded(
            child: PageView(
              controller: _pc,
              onPageChanged: (i) => setState(() => _idx = i),
              physics: const NeverScrollableScrollPhysics(),
              children: [_step1(), _step2(), _step3()],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _idx == 0
                    ? const SizedBox(width: 48)
                    : IconButton(
                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                  onPressed: () => _pc.previousPage(
                    duration: const Duration(milliseconds: 300),
                    curve: Curves.easeInOut,
                  ),
                ),
                Row(
                  children: [
                    if (currentUser != null)
                      TextButton(
                        onPressed: () => ScaffoldMessenger.of(context)
                            .showSnackBar(const SnackBar(
                            content: Text('This page is saved'))),
                        child: const Text('Save',
                            style: TextStyle(color: Colors.white)),
                      ),
                    const SizedBox(width: 8),
                    _idx == 2
                        ? ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF7e2c76),
                      ),
                      onPressed: _onSubmit,
                      child: const Text('Submit'),
                    )
                        : IconButton(
                      icon: const Icon(Icons.arrow_forward,
                          color: Colors.white),
                      onPressed: _validateAndNextPage,
                    ),
                  ],
                ),
              ],
            ),
          )
        ],
      ),
    );
  }

  /// STEP 1: Incident Details
  Widget _step1() {
    return Padding(
      padding: const EdgeInsets.all(18),
      child: ListView(
        children: [
          _label('Date of Incident *'),
          _inputWithIcon(_dateCtl,
              hint: 'DD/MM/YYYY',
              icon: Icons.calendar_today,
              onIconTap: _pickDate),
          const SizedBox(height: 12),
          _label('Time of Incident *'),
          _inputWithIcon(_timeCtl,
              hint: 'e.g., 3:30 PM',
              icon: Icons.access_time,
              onIconTap: _pickTime),
          const SizedBox(height: 12),
          _label('District *'),
          _dropdownWhiteBox(
            value: _selectedDistrict,
            hint: "Select District",
            items: districtUpazilaMap.keys.toList()..sort(),
            onChanged: (value) {
              setState(() {
                _selectedDistrict = value;
                _selectedUpazila = null;
              });
            },
          ),
          const SizedBox(height: 12),
          _label('Upazila *'),
          _dropdownWhiteBox(
            value: _selectedUpazila,
            hint: "Select Upazila",
            items: _selectedDistrict == null
                ? []
                : (districtUpazilaMap[_selectedDistrict]!..sort()),
            onChanged: (value) => setState(() => _selectedUpazila = value),
          ),
          const SizedBox(height: 12),
          _label('Types of Incidents'),
          ...incidentDescriptions.keys.map((key) {
            return ExpansionTile(
              title: Text(key, style: const TextStyle(color: Colors.white)),
              collapsedTextColor: Colors.white,
              textColor: Colors.white,
              iconColor: Colors.white,
              collapsedIconColor: Colors.white,
              children: [
                Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Text(
                    incidentDescriptions[key]!,
                    style: const TextStyle(color: Colors.white70),
                  ),
                ),
              ],
              onExpansionChanged: (expanded) {
                if (expanded) {
                  setState(() {
                    _type = key;
                  });
                }
              },
            );
          }).toList(),
        ],
      ),
    );
  }

  /// STEP 2: Description + File Upload
  Widget _step2() {
    return Padding(
      padding: const EdgeInsets.all(18),
      child: ListView(
        children: [
          _label('Describe What Happened (up to 5000 words) *'),
          _input(_descCtl, minLines: 6, maxLines: 12),
          const SizedBox(height: 12),
          _label('Upload supporting files (images/videos/audio/docs)'),
          const SizedBox(height: 8),
          _isUploading
              ? const Center(
              child: CircularProgressIndicator(color: Colors.white))
              : ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: const Color(0xFF7e2c76),
            ),
            onPressed: _pickAndUploadFile,
            child: const Text('Pick & Upload File'),
          ),
          if (_uploadedFileUrl != null)
            const Text("File uploaded successfully",
                style: TextStyle(color: Colors.greenAccent)),
        ],
      ),
    );
  }

  /// STEP 3: Confirmation + Contact (UNCHANGED)
  Widget _step3() {
    return Padding(
      padding: const EdgeInsets.all(18),
      child: ListView(
        children: [
          Row(
            children: [
              Checkbox(
                value: _confirmationChecked,
                onChanged: (v) =>
                    setState(() => _confirmationChecked = v ?? false),
                activeColor: Colors.white,
                checkColor: const Color(0xFF7e2c76),
              ),
              const Expanded(
                child: Text(
                  'The information provided in the reporting form are true *',
                  style: TextStyle(color: Colors.white),
                ),
              )
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Checkbox(
                value: _consentToBeContacted,
                onChanged: (v) {
                  setState(() => _consentToBeContacted = v ?? false);
                  if (_consentToBeContacted) _showPhoneDialog();
                },
                activeColor: Colors.white,
                checkColor: const Color(0xFF7e2c76),
              ),
              const Expanded(
                child: Text(
                  'During the procedure of processing your report do you want to be contacted?',
                  style: TextStyle(color: Colors.white),
                ),
              )
            ],
          ),
          if (_phoneNumber != null)
            Text(
              "Contact number provided: $_phoneNumber",
              style: const TextStyle(color: Colors.white70),
            ),
        ],
      ),
    );
  }

  /// Helper widgets, pickers, validation, file upload, submit... (keep all your original code unchanged)
  Widget _label(String text) => Text(
    text,
    style: const TextStyle(
        color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
  );

  Widget _input(TextEditingController controller,
      {String? hint, int minLines = 1, int maxLines = 1}) {
    return TextField(
      controller: controller,
      minLines: minLines,
      maxLines: maxLines,
      style: const TextStyle(color: Colors.white),
      decoration: const InputDecoration(
        enabledBorder:
        OutlineInputBorder(borderSide: BorderSide(color: Colors.white70)),
        focusedBorder:
        OutlineInputBorder(borderSide: BorderSide(color: Colors.white)),
      ),
    );
  }

  Widget _inputWithIcon(TextEditingController controller,
      {required IconData icon, required VoidCallback onIconTap, String? hint}) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white),
      readOnly: true,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white70),
        suffixIcon: IconButton(
            icon: Icon(icon, color: Colors.white), onPressed: onIconTap),
        enabledBorder:
        const OutlineInputBorder(borderSide: BorderSide(color: Colors.white70)),
        focusedBorder:
        const OutlineInputBorder(borderSide: BorderSide(color: Colors.white)),
      ),
    );
  }

  Widget _dropdownWhiteBox({
    required String? value,
    required String hint,
    required List<String> items,
    required ValueChanged<String?> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      dropdownColor: const Color(0xFF7e2c76),
      style: const TextStyle(color: Colors.white),
      value: value,
      hint: Text(hint, style: const TextStyle(color: Colors.white70)),
      icon: const Icon(Icons.arrow_drop_down, color: Colors.white),
      decoration: const InputDecoration(
        filled: true,
        fillColor: Colors.transparent,
        enabledBorder:
        OutlineInputBorder(borderSide: BorderSide(color: Colors.white70)),
        focusedBorder:
        OutlineInputBorder(borderSide: BorderSide(color: Colors.white)),
      ),
      items: items
          .map((e) => DropdownMenuItem(
        value: e,
        child: Text(e, style: const TextStyle(color: Colors.white)),
      ))
          .toList(),
      onChanged: onChanged,
    );
  }

  Future<void> _pickDate() async {
    final DateTime? picked = await showDatePicker(
        context: context,
        initialDate: DateTime.now(),
        firstDate: DateTime(2000),
        lastDate: DateTime.now());
    if (picked != null) {
      _dateCtl.text =
      "${picked.day.toString().padLeft(2, '0')}/${picked.month.toString().padLeft(2, '0')}/${picked.year}";
    }
  }

  Future<void> _pickTime() async {
    final TimeOfDay? picked =
    await showTimePicker(context: context, initialTime: TimeOfDay.now());
    if (picked != null) {
      _timeCtl.text =
      "${picked.hourOfPeriod.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')} ${picked.period == DayPeriod.am ? 'AM' : 'PM'}";
    }
  }

  void _validateAndNextPage() {
    if (_idx == 0) {
      if (_dateCtl.text.trim().isEmpty) { _showError("Please select the Date of Incident"); return; }
      if (_timeCtl.text.trim().isEmpty) { _showError("Please select the Time of Incident"); return; }
      if (_selectedDistrict == null) { _showError("Please select a District"); return; }
      if (_selectedUpazila == null) { _showError("Please select an Upazila"); return; }
      if (_type == null) { _showError("Please select the Type of Incident"); return; }
    }
    if (_idx == 1) {
      if (_descCtl.text.trim().isEmpty) { _showError("Please describe what happened"); return; }
    }
    _pc.nextPage(duration: const Duration(milliseconds: 300), curve: Curves.easeInOut);
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message), backgroundColor: Colors.red));
  }

  Future<void> _pickAndUploadFile() async {
    final result = await FilePicker.platform.pickFiles();
    if (result == null) return;
    setState(() { _pickedFile = File(result.files.single.path!); _isUploading = true; });
    try {
      final fileName = DateTime.now().millisecondsSinceEpoch.toString();
      final ref = FirebaseStorage.instance.ref().child('uploads').child(fileName);
      await ref.putFile(_pickedFile!);
      final url = await ref.getDownloadURL();
      setState(() { _uploadedFileUrl = url; _isUploading = false; });
    } catch (e) { setState(() => _isUploading = false); _showError("File upload failed: $e"); }
  }

  Future<void> _showPhoneDialog() async {
    String? tempPhone;
    await showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF7e2c76),
          title: const Text("Enter Phone Number", style: TextStyle(color: Colors.white)),
          content: IntlPhoneField(
            initialCountryCode: "BD",
            decoration: const InputDecoration(
              labelText: "Phone Number",
              labelStyle: TextStyle(color: Colors.white),
              enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white)),
              focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white)),
            ),
            style: const TextStyle(color: Colors.white),
            onChanged: (phone) { tempPhone = phone.completeNumber; },
          ),
          actions: [
            TextButton(
              onPressed: () { setState(() => _phoneNumber = tempPhone); Navigator.pop(context); },
              child: const Text("OK", style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }

  Future<void> _onSubmit() async {
    if (!_confirmationChecked) { _showError("Please confirm that the information is true"); return; }
    try {
      final currentUser = FirebaseAuth.instance.currentUser;
      if (currentUser == null) { _showError("No user logged in"); return; }
      final userDoc = await FirebaseFirestore.instance.collection('users').doc(currentUser.uid).get();
      if (!userDoc.exists) { _showError("User profile not found"); return; }
      final userData = userDoc.data() ?? {};
      await FirebaseFirestore.instance.collection('reports').add({
        "userId": currentUser.uid,
        "userName": userData["name"],
        "userEmail": userData["email"],
        "userPhone": userData["phone"],
        "date": _dateCtl.text,
        "time": _timeCtl.text,
        "district": _selectedDistrict,
        "upazila": _selectedUpazila,
        "type": _type,
        "description": _descCtl.text,
        "fileUrl": _uploadedFileUrl,
        "phoneNumber": _phoneNumber,
        "consentToBeContacted": _consentToBeContacted,
        "createdAt": Timestamp.now(),
      });
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text("Successfully submitted"),
          content: const Text("Your report has been submitted successfully."),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
                Navigator.of(context).pushNamedAndRemoveUntil('/home', (Route<dynamic> route) => false);
              },
              child: const Text("OK"),
            ),
          ],
        ),
      );
    } catch (e) { _showError("Failed to submit report: $e"); }
  }
}
