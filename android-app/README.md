# Little Library Atlas Android

This Android app lets contributors pick or take a shelf photo, read EXIF geolocation when present, review books manually, keep a phone copy, and sync the contribution to the central Little Library Atlas website.

The central website is the source of truth. Enter its public URL in the Capture tab, then use `Save + sync to website` to upload the reviewed library, geolocation, book metadata, and optional photo to `POST /api/mobile/libraries`.

## Build

1. Install Android Studio or the Android SDK with platform `android-36`.
2. Open `android-app` in Android Studio, or run:

```powershell
$env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT="$env:LOCALAPPDATA\Android\Sdk"
.\gradlew.bat assembleDebug
```

On Windows, the build output is redirected outside the OneDrive workspace to avoid Gradle file-lock issues:

```text
%LOCALAPPDATA%\LittleLibraryAtlasAndroidBuild\app\outputs\apk\debug\app-debug.apk
```

On Linux and in GitHub Actions, Gradle uses the standard project build directory.

## Connect to the central website

1. Deploy or start the website from the repo root.
2. Make it reachable from the phone. For local Wi-Fi testing, run the server with `HOST=0.0.0.0` and use a LAN URL such as `http://192.168.1.23:8000`.
3. Paste that URL into `Central website URL` in the Capture tab.
4. Capture or pick a shelf photo, review the books, then tap `Save + sync to website`.

The app allows cleartext HTTP so local testing is easy. Use HTTPS for a public deployment.

## Demo

The Atlas tab includes an `Import demo shelf` action that seeds the phone copy with the sample blue-library catalog without bundling the original source photo.
