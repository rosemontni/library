# Little Library Atlas Android

This Android app is a local-first companion to the web prototype. It lets someone pick or take a shelf photo, read EXIF geolocation when present, review books manually, store the catalog on-device, and search nearby matches without requiring the Python server.

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

## Demo

The Atlas tab includes an `Import demo shelf` action that seeds the app with the sample blue-library catalog without bundling the original source photo.
