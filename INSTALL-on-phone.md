# Install "UK Family Tour" on an Android phone

The app is fully offline once installed — no signal, wifi, or data needed on the trip.
File: **UK-Family-Tour-v1.apk** (~169 MB). Package: `com.family.uktour`.

## Easiest: install from Google Drive (each phone)

1. On the Android phone, open the **Drive** app → *London 2026* → *tour-app* →
   tap **UK-Family-Tour-v1.apk** to download it.
2. Open the downloaded file (Drive's Downloads, or the Files app).
3. Android will warn "For your security…" — tap **Settings → Allow from this source**
   (you're allowing your Files/Drive app to install this one app), then **Install**.
4. Open **UK Family Tour**. Done. You can turn on airplane mode and it still works.

Repeat on each family phone. Nothing to sign in to; no ads, no tracking, no network.

## Alternative: install by USB cable (from the Mac)

Needs the phone in developer mode:

1. Phone: Settings → About phone → tap **Build number** 7 times → developer mode on.
2. Settings → System → Developer options → enable **USB debugging**.
3. Plug the phone into the Mac; on the phone tap **Allow** for USB debugging.
4. On the Mac:
   ```sh
   adb install -r "/Users/ilya/projects/London-trip-vacation/tour-app/UK-Family-Tour-v1.apk"
   adb shell am start -n com.family.uktour/.MainActivity
   ```

## First-run check (proves it's the good offline build)

- Journey screen lists Days 2–14 with **photos** on the sight cards (not emoji).
- Turn on **airplane mode**, open *Tower of London* → Play. Audio plays and the
  player shows the **🎙 recorded-voice** icon (natural British narration), not 🤖.
- Toggle **Kids / Grown-ups** for the two versions; tap **✨ Tell me MORE!** for the
  deeper track; finishing all of a sight's tracks earns a gold **VISITED** passport stamp.

## Notes

- "Install unknown apps" is required only because this is a private family app, not
  from the Play Store. You can revoke that permission afterward.
- Content and photos (Wikipedia/Wikimedia) are for private family use.
