#!/usr/bin/env python3
"""
Explode Arena (Symbian S60) — Android APK Builder (Zero-Dependency SDK Script)

Builds a hardware-accelerated Android APK (WebGL GPU 4x xBR+Anime4K Upscaler,
Ergonomic Continuous-Slide D-Pad, Angled Arcade Bomb/Detonate Cluster, and
Native Android Haptic Feedback).

Usage:
  # 1. Build clean-room BYO-SIS APK (prompts user to select .sis on first launch):
  python3 tools/build_android_apk.py

  # 2. Build standalone APK with your own Explode_Arena.sis pre-bundled:
  python3 tools/build_android_apk.py /path/to/Explode_Arena.sis [output.apk]
"""

import os
import sys
import glob
import shutil
import base64
import struct
import zlib
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or os.path.expanduser("~/Library/Android/sdk")

bt_dirs = sorted(glob.glob(os.path.join(SDK, "build-tools", "*")))
plat_dirs = sorted(glob.glob(os.path.join(SDK, "platforms", "android-*")))
if not bt_dirs or not plat_dirs:
    sys.exit(f"Error: Android SDK build-tools/platforms not found under {SDK}")

BUILD_TOOLS = bt_dirs[-1]
ANDROID_JAR = os.path.join(plat_dirs[-1], "android.jar")
WORK = "/tmp/explode_arena_apk_build"

sis_input = sys.argv[1] if len(sys.argv) > 1 else None
out_apk = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO_DIR, "ExplodeArena-S60-HD.apk")

if os.path.exists(WORK):
    shutil.rmtree(WORK)
os.makedirs(f"{WORK}/src/im/agusibrah/explodearena", exist_ok=True)
os.makedirs(f"{WORK}/res/drawable", exist_ok=True)
os.makedirs(f"{WORK}/assets/js", exist_ok=True)
os.makedirs(f"{WORK}/classes", exist_ok=True)

def make_icon_png(path, W=192, H=192):
    raw = bytearray()
    cx, cy = W * 0.48, H * 0.56
    r = W * 0.32
    for y in range(H):
        raw.append(0)
        for x in range(W):
            dx_bg = max(abs(x - W/2) - (W/2 - 28), 0)
            dy_bg = max(abs(y - H/2) - (H/2 - 28), 0)
            if dx_bg*dx_bg + dy_bg*dy_bg > 28*28:
                raw.extend((0, 0, 0, 0))
                continue
            bg_r = int(18 + (H - y) * 0.08)
            bg_g = int(22 + (H - y) * 0.10)
            bg_b = int(32 + (H - y) * 0.14)
            sd = ((x - 132)**2 + (y - 46)**2) ** 0.5
            if sd < 26:
                t = 1.0 - sd / 26.0
                bg_r = min(255, int(bg_r + 255 * t))
                bg_g = min(255, int(bg_g + 190 * (t**1.3)))
                bg_b = min(255, int(bg_b + 60 * (t**2)))
            bd = ((x - cx)**2 + (y - cy)**2) ** 0.5
            if bd <= r:
                hd = ((x - (cx - r*0.35))**2 + (y - (cy - r*0.35))**2) ** 0.5
                spec = max(0.0, 1.0 - hd / (r * 0.55)) ** 2
                shade = max(0.15, 1.0 - (bd / r) * 0.7)
                pr = min(255, int(35 * shade + 210 * spec))
                pg = min(255, int(40 * shade + 215 * spec))
                pb = min(255, int(52 * shade + 230 * spec))
                raw.extend((pr, pg, pb, 255))
            else:
                raw.extend((bg_r, bg_g, bg_b, 255))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)

make_icon_png(f"{WORK}/res/drawable/ic_launcher.png")

manifest = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="im.agusibrah.explodearena"
    android:versionCode="2"
    android:versionName="2.0-GPU-HD">

    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.VIBRATE" />

    <application
        android:label="Explode Arena S60 HD"
        android:icon="@drawable/ic_launcher"
        android:hardwareAccelerated="true"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.NoTitleBar.Fullscreen">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="portrait"
            android:configChanges="orientation|screenSize|keyboardHidden|keyboard"
            android:hardwareAccelerated="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""
with open(f"{WORK}/AndroidManifest.xml", "w") as f:
    f.write(manifest)

java_code = """package im.agusibrah.explodearena;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private WebView webView;
    private Vibrator vibrator;
    private ValueCallback<Uri[]> filePathCallback;
    private static final int FILE_CHOOSER_REQ = 1001;

    public class AndroidBridge {
        @JavascriptInterface
        public void vibrate(int ms) {
            if (vibrator == null || !vibrator.hasVibrator()) return;
            try {
                int dur = Math.max(4, Math.min(ms, 50));
                if (Build.VERSION.SDK_INT >= 26) {
                    vibrator.vibrate(VibrationEffect.createOneShot(dur, 140));
                } else {
                    vibrator.vibrate(dur);
                }
            } catch (Exception ignored) {}
        }
    }

    private void applyImmersiveFullscreen() {
        Window w = getWindow();
        w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        View decor = w.getDecorView();
        decor.setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        applyImmersiveFullscreen();

        vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#0b0d11"));
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setVerticalScrollBarEnabled(false);
        webView.setHorizontalScrollBarEnabled(false);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setAllowFileAccessFromFileURLs(true);
        ws.setAllowUniversalAccessFromFileURLs(true);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView wv, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = cb;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                startActivityForResult(Intent.createChooser(intent, "Select .SIS / .SAV / .CFG File"), FILE_CHOOSER_REQ);
                return true;
            }
        });
        webView.setWebViewClient(new WebViewClient());

        setContentView(webView);
        webView.loadUrl("file:///android_asset/index.html");
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQ) {
            if (filePathCallback != null) {
                Uri[] results = null;
                if (resultCode == Activity.RESULT_OK && data != null && data.getData() != null) {
                    results = new Uri[]{ data.getData() };
                }
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) applyImmersiveFullscreen();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (webView != null) {
                webView.evaluateJavascript(
                    "if(window.__triggerRightSoftkey){window.__triggerRightSoftkey();}", null
                );
            }
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (webView != null) webView.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        applyImmersiveFullscreen();
        if (webView != null) webView.onResume();
    }
}
"""
with open(f"{WORK}/src/im/agusibrah/explodearena/MainActivity.java", "w") as f:
    f.write(java_code)

shutil.copy(os.path.join(REPO_DIR, "js/vm_wasm.js"), f"{WORK}/assets/js/vm_wasm.js")
shutil.copy(os.path.join(REPO_DIR, "js/sis_parser.js"), f"{WORK}/assets/js/sis_parser.js")

if sis_input and os.path.isfile(sis_input):
    with open(sis_input, "rb") as f:
        sis_b64 = base64.b64encode(f.read()).decode("ascii")
    with open(f"{WORK}/assets/js/builtin_sis.js", "w") as f:
        f.write(f'window.BUILTIN_SIS_BASE64 = "{sis_b64}";\n')
else:
    with open(f"{WORK}/assets/js/builtin_sis.js", "w") as f:
        f.write("// BYO-SIS mode: user selects .sis file on first launch\n")

with open(os.path.join(REPO_DIR, "index.html"), "r") as f:
    html = f.read()

android_css_extra = """
    /* Android APK GBA SP Clamshell Fullscreen Layout */
    body.android-apk .topbar {
      display: none;
    }
    body.android-apk .workspace {
      padding: 4px 6px 8px;
      gap: 8px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    body.android-apk .handheld-column {
      width: 100%;
    }
    body.android-apk .nokia-chassis {
      max-width: 440px;
      width: 100%;
    }
    body.android-apk .sp-upper-lid {
      padding: 10px 12px 10px;
    }
    body.android-apk .screen-bezel {
      padding: 8px 10px 10px;
    }
    body.android-apk .canvas-wrap {
      width: 100%;
      max-width: 330px;
      height: auto;
      max-height: 45dvh;
    }
    body.android-apk .sp-hinge {
      height: 28px;
    }
    body.android-apk .sp-lower-deck {
      padding: 12px 16px 18px;
    }
    body.android-apk .studio-deck {
      display: none;
      width: 100%;
      max-width: 440px;
    }
    body.android-apk.drawer-open .studio-deck {
      display: flex;
    }
"""

html = html.replace("</style>", android_css_extra + "\n  </style>")
html = html.replace("<body>", '<body class="android-apk">')
html = html.replace(
    '<script src="js/vm_wasm.js"></script>',
    '<script src="js/builtin_sis.js"></script>\n  <script src="js/vm_wasm.js"></script>'
)
html = html.replace(
    'document.getElementById("btn-toggle-numpad").addEventListener("click", (e) => {',
    '''window.__triggerRightSoftkey = () => { if (running) { hapticPulse(8); pulseKey(165); } };
      document.getElementById("btn-toggle-numpad").addEventListener("click", (e) => {
        document.body.classList.toggle("drawer-open");'''
)

with open(f"{WORK}/assets/index.html", "w") as f:
    f.write(html)

subprocess.run([f"{BUILD_TOOLS}/aapt2", "compile", "--dir", f"{WORK}/res", "-o", f"{WORK}/res.zip"], check=True)
subprocess.run([
    f"{BUILD_TOOLS}/aapt2", "link",
    "-I", ANDROID_JAR,
    "--manifest", f"{WORK}/AndroidManifest.xml",
    "--java", f"{WORK}/src",
    "-A", f"{WORK}/assets",
    "-o", f"{WORK}/unaligned.apk",
    f"{WORK}/res.zip"
], check=True)

java_files = [
    f"{WORK}/src/im/agusibrah/explodearena/MainActivity.java",
    f"{WORK}/src/im/agusibrah/explodearena/R.java"
]
subprocess.run([
    "javac", "-source", "1.8", "-target", "1.8",
    "-bootclasspath", ANDROID_JAR,
    "-classpath", ANDROID_JAR,
    "-d", f"{WORK}/classes"
] + java_files, check=True)

class_files = []
for root, _, files in os.walk(f"{WORK}/classes"):
    for fn in files:
        if fn.endswith(".class"):
            class_files.append(os.path.join(root, fn))

subprocess.run([
    f"{BUILD_TOOLS}/d8",
    "--lib", ANDROID_JAR,
    "--output", WORK
] + class_files, check=True)

subprocess.run(["zip", "-j", f"{WORK}/unaligned.apk", f"{WORK}/classes.dex"], check=True)
subprocess.run([f"{BUILD_TOOLS}/zipalign", "-f", "4", f"{WORK}/unaligned.apk", f"{WORK}/aligned.apk"], check=True)

ks = f"{WORK}/debug.keystore"
subprocess.run([
    "keytool", "-genkeypair", "-v",
    "-keystore", ks,
    "-storepass", "android",
    "-alias", "androiddebugkey",
    "-keypass", "android",
    "-keyalg", "RSA",
    "-keysize", "2048",
    "-validity", "10000",
    "-dname", "CN=Android Debug,O=Android,C=US"
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

subprocess.run([
    f"{BUILD_TOOLS}/apksigner", "sign",
    "--ks", ks,
    "--ks-pass", "pass:android",
    "--key-pass", "pass:android",
    "--out", out_apk,
    f"{WORK}/aligned.apk"
], check=True)

print(f"SUCCESS: Built Android APK -> {out_apk} ({os.path.getsize(out_apk):,} bytes)")
