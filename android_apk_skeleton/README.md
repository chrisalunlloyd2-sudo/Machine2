# VIPER APK Skeleton

This is an Android WebView shell for the VIPER Java SDK surface.

Current behavior:

```text
APK opens http://127.0.0.1:18181
theme matches the dark VIPER SDK style
Java SDK backend remains the authority for logs, benchmarks, epochs, and SHA-256 records
```

Important phone note:

```text
127.0.0.1 inside Android means the phone itself.
For a desktop/laptop SDK, change DEFAULT_SDK_URL in MainActivity.java to the LAN,
Cloudflare, or tunnel URL for that machine.
```

Build from this folder with Android Studio or a local Android Gradle setup:

```powershell
gradle :app:assembleDebug
```

This skeleton is intentionally thin. It does not yet embed the Java backend in
Android; it connects to an existing VIPER SDK endpoint or future phone-hosted
service.
