# Pitmark Race Center Android wrapper

Package: `com.pitmarkracing.racecenter`

This project wraps the installable Race Center PWA as a Trusted Web Activity (TWA).

## Current Play requirement
The app targets Android 16 / API 36 for new Google Play submissions.

## Release steps
1. Open `android-race-center` in Android Studio with JDK 17.
2. Install Android SDK Platform 36.
3. Generate an upload signing key and a signed Android App Bundle (AAB).
4. Copy the SHA-256 certificate fingerprint for the upload key into Render as `RACE_CENTER_ANDROID_SHA256`.
5. After Play App Signing is enabled, add the Play signing SHA-256 fingerprint to the same env var, comma-separated.
6. Verify `https://links.pitmarkracing.com/.well-known/assetlinks.json`.
7. Upload the signed AAB to Play Console closed testing.

The website remains the source of truth; normal Race Center updates deploy through PitmarkCloud without requiring a new Android binary unless native wrapper metadata changes.
