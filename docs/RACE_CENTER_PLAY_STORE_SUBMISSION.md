# Pitmark Race Center — Google Play Submission Pack

Prepared: September 24, 2026

## App identity
- App title: Pitmark Race Center
- Package ID: com.pitmarkracing.racecenter
- Default language: English (United States)
- Category: Sports
- Website: https://links.pitmarkracing.com/race-center
- Privacy / account deletion URL: https://links.pitmarkracing.com/race-center/privacy
- Developer contact: justin@pitmarkracing.com

## Store listing

### Short description
Live racing, schedules, results, drivers, tracks, and your racing follows.

### Full description
Pitmark Race Center brings the racing you follow into one connected home.

See what is live and what is coming next, browse drivers, teams, tracks and series, check schedules and standings, and build a personal My Racing view around the people and championships you care about.

Race Center connects:
- Live and upcoming race information
- Driver, team, track and series pages
- Schedules and standings
- Racing stories and public updates
- Local and grassroots racing discovery
- Saved follows and a personalized My Racing view
- Community profiles, posts and racing conversations

Race information is assembled from official and public racing sources where available, with source links included throughout the experience.

A Race Center account is optional for browsing. Signing in adds saved follows, profile and community features across devices.

Pitmark Race Center is built by Pitmark Racing Co. for racing fans, drivers, teams, tracks and series.

## Play Console content notes

### Target audience
Recommended initial declaration: 18+ / not designed for children.
Reason: open racing community features and user-generated content are part of Race Center.

### App access
Most Race Center content is publicly accessible without signing in.
Account-only features include saved follows, profile editing, posting/commenting, claims, and owner-managed content.

Before review, create a dedicated Play review account only if Google requests credentials for account-only surfaces.

### Ads
Race Center currently has no Android advertising SDK in the wrapper project.
Verify the live website does not introduce advertising SDKs before answering the Play Console ads question.

### Account deletion
In-app path:
My Race Center → Delete Account

External path:
https://links.pitmarkracing.com/race-center/privacy#delete-account

### Data safety working draft
Verify in Play Console before submission.

Data handled by Race Center account/community features includes:
- Email address — account management / authentication
- Name or display name — account/profile functionality
- User IDs / handles — account/profile functionality
- Profile photos — optional user-provided profile content
- User-generated content — posts, comments, reactions, claims and owner-managed racing content
- Saved racing follows/preferences — personalization / app functionality

The Android wrapper itself requests INTERNET permission only.

Do not mark precise location, contacts, microphone, SMS, call logs, health data or financial information as collected unless those capabilities are later added.

## Technical submission status
- [x] PWA manifest
- [x] Service worker
- [x] Standalone install mode
- [x] 192px and 512px web app icons
- [x] Mobile app shell / bottom navigation
- [x] Android TWA project scaffold
- [x] Package ID reserved in source
- [x] targetSdk 36
- [x] Deep-link intent filter for links.pitmarkracing.com/race-center
- [x] /.well-known/assetlinks.json endpoint
- [x] Privacy / data page
- [x] In-app account deletion
- [x] External account deletion path
- [ ] Generate release upload keystore
- [ ] Build signed AAB
- [ ] Add upload-key SHA-256 fingerprint to RACE_CENTER_ANDROID_SHA256
- [ ] Create Play Console app
- [ ] Enable Play App Signing
- [ ] Add Play signing SHA-256 fingerprint to RACE_CENTER_ANDROID_SHA256
- [ ] Verify Digital Asset Links
- [ ] Capture final phone screenshots from production
- [ ] Create 512×512 Play icon asset
- [ ] Create 1024×500 feature graphic
- [ ] Complete content rating questionnaire
- [ ] Complete Data safety questionnaire
- [ ] Complete target audience declaration
- [ ] Start closed testing if required by the developer account
