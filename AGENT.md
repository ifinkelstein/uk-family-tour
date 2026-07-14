# AGENT.md — build & install runbook

Instructions for a coding agent (Claude Code, etc.) or a patient human to take
this folder from source to a fully offline app running on an Android phone.
Target machine: macOS (Apple Silicon or Intel). Everything is free.

## Goal / definition of done

1. `scripts/verify_assets.py` exits 0 (all 220 audio tracks rendered with
   Kokoro voices + all sight images bundled).
2. `./gradlew :app:assembleDebug` produces `app/build/outputs/apk/debug/app-debug.apk`.
3. APK installed on the connected phone and launches to the Journey screen.
4. Airplane-mode check: app plays a story with the 🎙 icon and shows photos.

## Phase 0 — toolchain

```bash
# Homebrew if absent: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install --cask temurin@17          # JDK 17 (required by AGP 8.5)
brew install gradle android-commandlinetools android-platform-tools \
             espeak-ng ffmpeg python@3.12

export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export ANDROID_HOME="$(brew --prefix)/share/android-commandlinetools"
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

Sanity: `java -version` → 17.x, `sdkmanager --list_installed` shows android-34,
`adb version` works.

## Phase 1 — offline assets (images + voices)

```bash
cd scripts
chmod +x prepare_assets.sh
./prepare_assets.sh
```

This downloads each sight's Wikipedia lead images into
`app/src/main/assets/tour/images/` and renders all 220 tracks (~3h of audio)
to MP3 in `app/src/main/assets/tour/audio/` using Kokoro-82M
(British voices: bf_emma for kid tracks, bm_george for adult).
~20–45 min on Apple Silicon; the model (~330MB) downloads on first run.

Checks & recovery:
- `python3 verify_assets.py` must exit 0 before proceeding.
- If a few images were skipped (Wikipedia article renamed), either rerun,
  or edit the offending title in `app/src/main/assets/tour/images.json` to
  the current article name and rerun `fetch_images.py`. Only index-0 images
  are strictly required; others are per-track nice-to-haves.
- If Kokoro import fails on Python 3.13, use python3.12 for the venv:
  `rm -rf venv && python3.12 -m venv venv` and rerun.
- Resume is automatic: both scripts skip files that already exist.
- GPU alternative: run the Colab recipe in the header of
  `generate_audio.py`, then unzip its output into
  `app/src/main/assets/tour/audio/`.

## Phase 2 — compile

The zip ships without a Gradle wrapper; generate one with brew's Gradle
(one time), then use the wrapper:

```bash
cd <project root>            # folder containing settings.gradle.kts
echo "sdk.dir=$ANDROID_HOME" > local.properties
gradle wrapper --gradle-version 8.9
./gradlew :app:assembleDebug
```

Expected: `BUILD SUCCESSFUL`, APK at
`app/build/outputs/apk/debug/app-debug.apk` (roughly 150–250MB thanks to the
bundled audio).

Troubleshooting:
- "SDK location not found" → local.properties path wrong; use absolute path.
- AGP/Gradle version complaint → keep Gradle 8.7–8.9 with AGP 8.5.2, or
  bump the AGP version in the root build.gradle.kts to what the error suggests.
- Kotlin/Compose compile errors: fix forward — the codebase is small
  (3 Kotlin files); typical issues are missing imports. Do not downgrade
  the compose BOM below 2024.05 (the lambda-based LinearProgressIndicator
  API is used).
- If asset compression makes builds slow, that's normal for 200MB of mp3;
  aaptOptions noCompress is unnecessary (mp3 is stored uncompressed by default).

## Phase 3 — install & launch

Phone: enable Developer options → USB debugging, plug in, accept the prompt.

```bash
adb devices                        # must list the phone as "device"
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.family.uktour/.MainActivity
```

For additional family phones, either repeat adb install, or share the APK
file directly (AirDrop/Drive) — recipients tap it and allow
"install unknown apps".

## Phase 4 — smoke test (do all of these)

1. Journey screen shows Days 2–14 with photos on sight cards (not emoji —
   emoji means images weren't bundled).
2. Enable airplane mode on the phone. Open "Tower of London" → press play:
   audio plays, player shows 🎙 (recorded voice), NOT 🤖 (device TTS).
3. Pause mid-sentence, resume — playback continues.
4. Tap "✨ Tell me MORE!" — an extension track plays, then the tour continues.
5. Toggle Kids/Grown-ups — same sight, different track list.
6. Let a sight's tracks finish → Passport screen shows a gold VISITED stamp.
7. Kill and reopen the app — checkmarks persisted.

If step 2 shows 🤖: audio assets missing from the APK — rerun
`verify_assets.py`, confirm files are under `app/src/main/assets/tour/audio/`,
and rebuild.

## Layout reference

    app/src/main/assets/tour/
      manifest.json      playlists (single source of truth)
      images.json        sight → emoji, color, Wikipedia titles
      content/           220 narration .md files (kid/adult × base/more)
      images/            <sight-id>-<n>.jpg        (created in Phase 1)
      audio/             mirrors content/, .mp3    (created in Phase 1)
    scripts/
      prepare_assets.sh  one-command Phase 1
      fetch_images.py    images only
      generate_audio.py  voices only (Kokoro-82M)
      verify_assets.py   completeness gate
