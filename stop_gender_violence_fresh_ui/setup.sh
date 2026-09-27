#!/bin/bash
# Creates platform folders and gets packages.
echo "Running flutter create . to generate platform folders (v2 embedding)."
flutter create .
flutter pub get
echo "Done. You can now run: flutter run"
