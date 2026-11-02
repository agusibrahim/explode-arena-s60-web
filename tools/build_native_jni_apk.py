#!/usr/bin/env python3
"""
Explode Arena (Symbian S60) — Pure Native C / JNI + OpenGL ES 2.0 Android APK Builder
(ZERO WebView, ZERO JavaScript, ZERO WebAssembly)

Compiles `src/vm.c` directly into native ARM64 (`arm64-v8a`) and ARMv7 (`armeabi-v7a`)
shared libraries (`libexplodevm.so`) using the Android NDK, paired with:
  - Pure OpenGL ES 2.0 `GLSurfaceView` running the 4x xBR + Anime4K + De-Dither GLSL shader
  - Pure Native Android `AudioTrack` (16,000 Hz 16-bit PCM low-latency audio thread)
  - Pure Native Android Custom-Drawn GBA SP Dark Matte Clamshell UI (`Canvas` + Multi-Touch)
  - Zero-Config UDP Broadcast LAN Multiplayer (`DatagramSocket` port 18765)

Usage:
  # 1. Build clean-room BYO-SIS Native JNI APK:
  python3 tools/build_native_jni_apk.py

  # 2. Build standalone Native JNI APK with Explode_Arena.sis pre-bundled:
  python3 tools/build_native_jni_apk.py /path/to/Explode_Arena.sis [output.apk]
"""

import os
import sys
import glob
import shutil
import struct
import zlib
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or os.path.expanduser("~/Library/Android/sdk")

bt_dirs = sorted(glob.glob(os.path.join(SDK, "build-tools", "*")))
plat_dirs = sorted(glob.glob(os.path.join(SDK, "platforms", "android-*")))
ndk_dirs = sorted(glob.glob(os.path.join(SDK, "ndk", "*")))
if not bt_dirs or not plat_dirs or not ndk_dirs:
    sys.exit(f"Error: Android SDK build-tools, platforms, or ndk not found under {SDK}")

BUILD_TOOLS = bt_dirs[-1]
ANDROID_JAR = os.path.join(plat_dirs[-1], "android.jar")
NDK_BIN = None
for ndk in reversed(ndk_dirs):
    cand = glob.glob(os.path.join(ndk, "toolchains", "llvm", "prebuilt", "*", "bin"))
    if cand and os.path.isfile(os.path.join(cand[0], "aarch64-linux-android24-clang")):
        NDK_BIN = cand[0]
        break
if not NDK_BIN:
    sys.exit("Error: NDK clang toolchain not found")

WORK = "/tmp/explode_arena_native_jni_build"
sis_input = sys.argv[1] if len(sys.argv) > 1 else None
out_apk = sys.argv[2] if len(sys.argv) > 2 else os.path.join(REPO_DIR, "ExplodeArena-S60-Native-JNI.apk")

if os.path.exists(WORK):
    shutil.rmtree(WORK)
os.makedirs(f"{WORK}/src/im/agusibrah/explodearena/jni", exist_ok=True)
os.makedirs(f"{WORK}/res/drawable", exist_ok=True)
os.makedirs(f"{WORK}/assets", exist_ok=True)
os.makedirs(f"{WORK}/lib/arm64-v8a", exist_ok=True)
os.makedirs(f"{WORK}/lib/armeabi-v7a", exist_ok=True)
os.makedirs(f"{WORK}/classes", exist_ok=True)

# 1. Compile src/vm.c into native ARM64 & ARMv7 shared libraries (libexplodevm.so)
vm_c = os.path.join(REPO_DIR, "src", "vm.c")
subprocess.run([
    os.path.join(NDK_BIN, "aarch64-linux-android24-clang"),
    "-O3", "-shared", "-fPIC", "-Wl,-s",
    vm_c, "-o", f"{WORK}/lib/arm64-v8a/libexplodevm.so"
], check=True)

subprocess.run([
    os.path.join(NDK_BIN, "armv7a-linux-androideabi24-clang"),
    "-O3", "-shared", "-fPIC", "-Wl,-s",
    vm_c, "-o", f"{WORK}/lib/armeabi-v7a/libexplodevm.so"
], check=True)

# 2. Bundle Explode_Arena.sis into assets/game.sis if provided
if sis_input and os.path.isfile(sis_input):
    shutil.copy(sis_input, f"{WORK}/assets/game.sis")

# 3. Generate 192x192 PNG Launcher Icon
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

# 4. Write AndroidManifest.xml
manifest = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="im.agusibrah.explodearena.jni"
    android:versionCode="2"
    android:versionName="2.0-Native-JNI">

    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
    <uses-feature android:glEsVersion="0x00020000" android:required="true" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
    <uses-permission android:name="android.permission.VIBRATE" />

    <application
        android:label="Explode Arena SP (JNI)"
        android:icon="@drawable/ic_launcher"
        android:hardwareAccelerated="true"
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

# 5. Write NativeVm.java
native_vm_java = """package im.agusibrah.explodearena.jni;

import java.nio.ByteBuffer;

public class NativeVm {
    static {
        System.loadLibrary("explodevm");
    }

    public static final Object VM_LOCK = new Object();

    public static native void initVm(byte[] codeBytes, byte[] pakBytes, byte[] cfgBytes, int uid);
    public static native void tick(int dtMs);
    public static native void keyEvent(int scanCode, int pressed);
    public static native void copyNativeRgba(ByteBuffer directRgbaBuf);
    public static native void mixAudio(short[] outPcm768);
    public static native void applyCheat(int cheatId);
    public static native boolean consumeCfgDirty(byte[] outCfg104);
    public static native int mpGetRole();
    public static native int mpGetState();
    public static native boolean mpIsWaiting();
    public static native int mpPopTx(byte[] outPayload);
    public static native void mpPushRx(byte[] inPayload, int len);
}
"""
with open(f"{WORK}/src/im/agusibrah/explodearena/jni/NativeVm.java", "w") as f:
    f.write(native_vm_java)

# 6. Write MainActivity.java (Pure Native OpenGL ES 2.0 + AudioTrack + GBA SP Clamshell Custom Views + UDP LAN Netplay)
main_java = r"""package im.agusibrah.explodearena.jni;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.InterfaceAddress;
import java.net.NetworkInterface;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.Inflater;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

public class MainActivity extends Activity {
    private static final int PICK_SIS_REQ = 2001;
    private static final int UDP_PORT = 18765;
    private static final String PREFS_NAME = "ExplodeArenaSpPrefs";

    private Vibrator vibrator;
    private SharedPreferences prefs;
    private GLSurfaceView glView;
    private TextView tvTopLeft;
    private TextView tvTopRight;
    private GbaSpDeckView deckView;

    private volatile boolean vmInitialized = false;
    private volatile boolean paused = false;
    private volatile boolean audioMuted = false;
    private volatile boolean godMode = false;
    private volatile int upscaleMode = 2; // 0=1x, 1=xBR 4x, 2=xBR+Anime4K 4x
    private volatile int targetSimFps = 30;
    private volatile int currentGlFps = 60;
    private volatile int currentSimTps = 30;
    private int alienCycle = 4;
    private int localUid;

    private byte[] cachedCodeBytes;
    private byte[] cachedPakBytes;
    private ByteBuffer directFrameBuf;

    // Key hold guarantee (at least 2 VM ticks per tap)
    private volatile int tickCounter = 0;
    private final int[] keyDownTick = new int[256];
    private final boolean[] keyIsDown = new boolean[256];
    private final boolean[] pendingKeyUp = new boolean[256];

    private Thread simThread;
    private Thread audioThread;
    private Thread udpRxThread;
    private DatagramSocket udpSocket;
    private WifiManager.MulticastLock multicastLock;
    private final ConcurrentHashMap<InetAddress, Long> knownPeers = new ConcurrentHashMap<>();
    private volatile boolean runningThreads = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        applyImmersive();

        vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        localUid = new Random().nextInt(0x7ffffffe) + 1;
        directFrameBuf = ByteBuffer.allocateDirect(176 * 208 * 4).order(ByteOrder.nativeOrder());

        try {
            WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm != null) {
                multicastLock = wm.createMulticastLock("ExplodeArenaLanLock");
                multicastLock.setReferenceCounted(false);
                multicastLock.acquire();
            }
        } catch (Exception ignored) {}

        setContentView(buildGbaSpClamshellUi());

        // Try booting from bundled assets/game.sis or cached preferences
        if (!tryBootBundledOrCachedSis()) {
            promptPickSisFile();
        }

        startEngineThreads();
    }

    private void applyImmersive() {
        Window w = getWindow();
        w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        w.getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );
    }

    private int dp(float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics()));
    }

    private void vibrateTick(int ms) {
        if (vibrator == null || !vibrator.hasVibrator()) return;
        try {
            int d = Math.max(4, Math.min(ms, 40));
            if (Build.VERSION.SDK_INT >= 26) {
                vibrator.vibrate(VibrationEffect.createOneShot(d, 145));
            } else {
                vibrator.vibrate(d);
            }
        } catch (Exception ignored) {}
    }

    private View buildGbaSpClamshellUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#0c0c0e"));
        root.setPadding(dp(6), dp(6), dp(6), dp(6));

        // 1. Upper Clamshell Lid (52% height)
        LinearLayout upperLid = new LinearLayout(this) {
            private final Paint borderPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
            private final RectF rect = new RectF();
            @Override
            protected void dispatchDraw(Canvas canvas) {
                rect.set(0, 0, getWidth(), getHeight());
                borderPaint.setStyle(Paint.Style.FILL);
                borderPaint.setColor(Color.parseColor("#18181c"));
                canvas.drawRoundRect(rect, dp(26), dp(26), borderPaint);
                borderPaint.setStyle(Paint.Style.STROKE);
                borderPaint.setStrokeWidth(dp(2));
                borderPaint.setColor(Color.parseColor("#292930"));
                canvas.drawRoundRect(rect, dp(26), dp(26), borderPaint);
                super.dispatchDraw(canvas);
            }
        };
        upperLid.setOrientation(LinearLayout.VERTICAL);
        upperLid.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams upperLp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 0.53f
        );
        root.addView(upperLid, upperLp);

        // Inner Black Screen Bezel Lens
        LinearLayout bezel = new LinearLayout(this) {
            private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
            private final RectF r = new RectF();
            @Override
            protected void dispatchDraw(Canvas canvas) {
                r.set(0, 0, getWidth(), getHeight());
                p.setColor(Color.BLACK);
                canvas.drawRoundRect(r, dp(18), dp(18), p);
                super.dispatchDraw(canvas);
            }
        };
        bezel.setOrientation(LinearLayout.VERTICAL);
        bezel.setGravity(Gravity.CENTER_HORIZONTAL);
        bezel.setPadding(dp(10), dp(8), dp(10), dp(8));
        upperLid.addView(bezel, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
        ));

        // Top Screen Status Bar ("POWER ON" | "BATTERY FULL")
        LinearLayout metaBar = new LinearLayout(this);
        metaBar.setOrientation(LinearLayout.HORIZONTAL);
        tvTopLeft = new TextView(this);
        tvTopLeft.setText("POWER ON");
        tvTopLeft.setTextColor(Color.parseColor("#6c6f78"));
        tvTopLeft.setTextSize(TypedValue.COMPLEX_UNIT_SP, 10);
        tvTopLeft.setTypeface(Typeface.DEFAULT_BOLD);

        tvTopRight = new TextView(this);
        tvTopRight.setText("BATTERY FULL");
        tvTopRight.setTextColor(Color.parseColor("#6c6f78"));
        tvTopRight.setTextSize(TypedValue.COMPLEX_UNIT_SP, 10);
        tvTopRight.setTypeface(Typeface.DEFAULT_BOLD);
        tvTopRight.setGravity(Gravity.END);

        metaBar.addView(tvTopLeft, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        metaBar.addView(tvTopRight, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        bezel.addView(metaBar, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        // Center Aspect-Ratio Locked Container for OpenGL ES 2.0 GLSurfaceView (176:208)
        FrameLayout screenHolder = new FrameLayout(this) {
            @Override
            protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
                int w = MeasureSpec.getSize(widthMeasureSpec);
                int h = MeasureSpec.getSize(heightMeasureSpec);
                int targetW = Math.round(h * (176f / 208f));
                int targetH = h;
                if (targetW > w) {
                    targetW = w;
                    targetH = Math.round(w * (208f / 176f));
                }
                super.onMeasure(
                    MeasureSpec.makeMeasureSpec(targetW, MeasureSpec.EXACTLY),
                    MeasureSpec.makeMeasureSpec(targetH, MeasureSpec.EXACTLY)
                );
            }
        };
        LinearLayout.LayoutParams shLp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
        );
        shLp.topMargin = dp(4);
        shLp.bottomMargin = dp(4);
        bezel.addView(screenHolder, shLp);

        glView = new GLSurfaceView(this);
        glView.setEGLContextClientVersion(2);
        glView.setRenderer(new SpGlRenderer());
        glView.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);
        screenHolder.addView(glView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.CENTER
        ));

        // Bottom GBA SP Silver Italic Badge
        TextView logoTv = new TextView(this);
        logoTv.setText("GAME BOY ADVANCE SP");
        logoTv.setTextColor(Color.parseColor("#e2e8f0"));
        logoTv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        logoTv.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD_ITALIC));
        logoTv.setLetterSpacing(0.06f);
        logoTv.setGravity(Gravity.CENTER);
        bezel.addView(logoTv, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        // 2. Middle 3D Cylindrical Clamshell Hinge
        View hingeView = new View(this) {
            private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
            @Override
            protected void onDraw(Canvas c) {
                int w = getWidth(), h = getHeight();
                p.setShader(new LinearGradient(
                    0, 0, 0, h,
                    new int[]{0xFF08080A, 0xFF2D2D33, 0xFF1E1E23, 0xFF070709},
                    new float[]{0f, 0.30f, 0.68f, 1f},
                    Shader.TileMode.CLAMP
                ));
                c.drawRect(dp(4), 0, w - dp(4), h, p);
                p.setShader(null);
                p.setColor(0xFF0A0A0D);
                p.setStrokeWidth(dp(2));
                c.drawLine(w * 0.14f, 0, w * 0.14f, h, p);
                c.drawLine(w * 0.50f, 0, w * 0.50f, h, p);
                c.drawLine(w * 0.86f, 0, w * 0.86f, h, p);
            }
        };
        root.addView(hingeView, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(28)
        ));

        // 3. Lower Clamshell Controller Deck (47% height, Pure Native Multi-Touch Canvas)
        deckView = new GbaSpDeckView(this);
        root.addView(deckView, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 0.47f
        ));

        return root;
    }

    // Pure Java Symbian EPOC R6 .SIS & E32 Image Unpacker (uses built-in java.util.zip.Inflater)
    private boolean bootFromSisStream(InputStream is, boolean saveCache) {
        try {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = is.read(buf)) > 0) bos.write(buf, 0, n);
            byte[] sis = bos.toByteArray();
            if (sis.length < 0x80) return false;

            ByteBuffer bb = ByteBuffer.wrap(sis).order(ByteOrder.LITTLE_ENDIAN);
            int uid3 = bb.getInt(0x08);
            if (uid3 != 0x10000419) return false;

            int nfiles = bb.getShort(0x14) & 0xffff;
            int pfiles = bb.getInt(0x34);

            byte[] foundPak = null;
            byte[] foundCode = null;

            for (int i = 0; i < nfiles; i++) {
                int off = pfiles + i * 0x30;
                if (off + 0x28 > sis.length) break;
                int fnLen = bb.getInt(off + 0x14);
                int fnPtr = bb.getInt(off + 0x18);
                int fLen  = bb.getInt(off + 0x1c);
                int fPtr  = bb.getInt(off + 0x20);
                int uLen  = bb.getInt(off + 0x24);

                String name = "";
                if (fnPtr >= 0 && fnLen > 0 && fnPtr + fnLen <= sis.length) {
                    StringBuilder sb = new StringBuilder();
                    for (int k = 0; k < fnLen; k += 2) {
                        sb.append((char) (sis[fnPtr + k] & 0xff));
                    }
                    name = sb.toString().toLowerCase();
                }
                if (fPtr > 0 && fLen > 0 && fPtr + fLen <= sis.length) {
                    byte[] raw;
                    if (fLen == uLen) {
                        raw = new byte[fLen];
                        System.arraycopy(sis, fPtr, raw, 0, fLen);
                    } else {
                        raw = inflateZlib(sis, fPtr, fLen, uLen > fLen ? uLen : fLen * 4);
                    }
                    if (name.endsWith("data.pak")) {
                        foundPak = raw;
                    } else if (name.endsWith(".app") && raw.length > 0x7c) {
                        ByteBuffer ebb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
                        int codeSz = ebb.getInt(0x30);
                        int codeOff = ebb.getInt(0x64);
                        if (codeOff > 0 && codeSz > 0 && codeOff + codeSz <= raw.length) {
                            foundCode = new byte[codeSz];
                            System.arraycopy(raw, codeOff, foundCode, 0, codeSz);
                        }
                    }
                }
            }

            if (foundPak == null || foundCode == null) return false;
            cachedPakBytes = foundPak;
            cachedCodeBytes = foundCode;

            byte[] savedCfg = null;
            String cfgB64 = prefs.getString("game_cfg_b64", null);
            if (cfgB64 != null) {
                try { savedCfg = Base64.decode(cfgB64, Base64.DEFAULT); } catch (Exception ignored) {}
            }

            synchronized (NativeVm.VM_LOCK) {
                NativeVm.initVm(cachedCodeBytes, cachedPakBytes, savedCfg, localUid);
                NativeVm.copyNativeRgba(directFrameBuf);
                vmInitialized = true;
            }

            if (saveCache) {
                try {
                    java.io.File outF = new java.io.File(getFilesDir(), "cached_game.sis");
                    java.io.FileOutputStream fos = new java.io.FileOutputStream(outF);
                    fos.write(sis);
                    fos.close();
                } catch (Exception ignored) {}
            }
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private static byte[] inflateZlib(byte[] src, int off, int len, int expectedSize) throws Exception {
        Inflater inf = new Inflater();
        inf.setInput(src, off, len);
        ByteArrayOutputStream out = new ByteArrayOutputStream(Math.max(expectedSize, 4096));
        byte[] tmp = new byte[16384];
        while (!inf.finished()) {
            int count = inf.inflate(tmp);
            if (count <= 0) {
                if (inf.needsInput() || inf.needsDictionary()) break;
                break;
            }
            out.write(tmp, 0, count);
        }
        inf.end();
        return out.toByteArray();
    }

    private boolean tryBootBundledOrCachedSis() {
        try {
            InputStream ais = getAssets().open("game.sis");
            boolean ok = bootFromSisStream(ais, false);
            ais.close();
            if (ok) return true;
        } catch (Exception ignored) {}

        try {
            java.io.File f = new java.io.File(getFilesDir(), "cached_game.sis");
            if (f.exists() && f.length() > 100) {
                java.io.FileInputStream fis = new java.io.FileInputStream(f);
                boolean ok = bootFromSisStream(fis, false);
                fis.close();
                if (ok) return true;
            }
        } catch (Exception ignored) {}
        return false;
    }

    private void promptPickSisFile() {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(Intent.createChooser(intent, "Select Explode_Arena.sis"), PICK_SIS_REQ);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == PICK_SIS_REQ && resultCode == Activity.RESULT_OK && data != null && data.getData() != null) {
            try {
                InputStream is = getContentResolver().openInputStream(data.getData());
                if (is != null && bootFromSisStream(is, true)) {
                    is.close();
                    Toast.makeText(this, "Explode Arena booted natively via JNI!", Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(this, "Invalid .SIS file!", Toast.LENGTH_LONG).show();
                }
            } catch (Exception e) {
                Toast.makeText(this, "Error loading .SIS: " + e.getMessage(), Toast.LENGTH_LONG).show();
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    public void sendVmKey(int scanCode, boolean pressed) {
        if (!vmInitialized) return;
        int idx = scanCode & 0xff;
        synchronized (NativeVm.VM_LOCK) {
            if (pressed) {
                pendingKeyUp[idx] = false;
                keyDownTick[idx] = tickCounter;
                keyIsDown[idx] = true;
                NativeVm.keyEvent(scanCode, 1);
            } else {
                if (keyIsDown[idx] && (tickCounter - keyDownTick[idx]) < 2) {
                    pendingKeyUp[idx] = true;
                } else {
                    keyIsDown[idx] = false;
                    pendingKeyUp[idx] = false;
                    NativeVm.keyEvent(scanCode, 0);
                }
            }
        }
    }

    public void pulseVmKey(int scanCode) {
        sendVmKey(scanCode, true);
        sendVmKey(scanCode, false);
    }

    private void flushPendingKeyUpsLocked() {
        for (int s = 0; s < 256; s++) {
            if (pendingKeyUp[s] && (tickCounter - keyDownTick[s]) >= 2) {
                pendingKeyUp[s] = false;
                keyIsDown[s] = false;
                NativeVm.keyEvent(s, 0);
            }
        }
    }

    private List<InetAddress> getLanBroadcastTargets() {
        List<InetAddress> targets = new ArrayList<>();
        try {
            Enumeration<NetworkInterface> nis = NetworkInterface.getNetworkInterfaces();
            while (nis != null && nis.hasMoreElements()) {
                NetworkInterface ni = nis.nextElement();
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InterfaceAddress ia : ni.getInterfaceAddresses()) {
                    InetAddress addr = ia.getAddress();
                    if (!(addr instanceof Inet4Address)) continue;
                    InetAddress bcast = ia.getBroadcast();
                    if (bcast != null && !targets.contains(bcast)) {
                        targets.add(bcast);
                    }
                    // Also add subnet .1 gateway (Hotspot host phone is always x.x.x.1!)
                    byte[] ip = addr.getAddress();
                    if (ip.length == 4 && (ip[3] & 0xff) != 1) {
                        ip[3] = 1;
                        InetAddress gw = InetAddress.getByAddress(ip);
                        if (!targets.contains(gw)) targets.add(gw);
                    }
                }
            }
        } catch (Exception ignored) {}
        try {
            InetAddress globalBcast = InetAddress.getByName("255.255.255.255");
            if (!targets.contains(globalBcast)) targets.add(globalBcast);
        } catch (Exception ignored) {}
        return targets;
    }

    private void sendUdpPacketToPeers(byte[] pkt, boolean alsoBroadcast) {
        if (udpSocket == null || udpSocket.isClosed()) return;
        long now = System.currentTimeMillis();
        int sentUnicast = 0;
        for (Map.Entry<InetAddress, Long> entry : knownPeers.entrySet()) {
            if (now - entry.getValue() > 15000) {
                knownPeers.remove(entry.getKey());
                continue;
            }
            try {
                udpSocket.send(new DatagramPacket(pkt, pkt.length, entry.getKey(), UDP_PORT));
                sentUnicast++;
            } catch (Exception ignored) {}
        }
        if (alsoBroadcast || sentUnicast == 0) {
            for (InetAddress bcast : getLanBroadcastTargets()) {
                try {
                    udpSocket.send(new DatagramPacket(pkt, pkt.length, bcast, UDP_PORT));
                } catch (Exception ignored) {}
            }
        }
    }

    private void sendDiscoveryBeacon() {
        new Thread(new Runnable() {
            @Override
            public void run() {
                byte[] ping = new byte[]{
                    (byte) (localUid & 0xff),
                    (byte) ((localUid >> 8) & 0xff),
                    (byte) ((localUid >> 16) & 0xff),
                    (byte) ((localUid >> 24) & 0xff),
                    (byte) 0xfd,
                    (byte) 0x01
                };
                sendUdpPacketToPeers(ping, true);
                if (knownPeers.isEmpty() && udpSocket != null && !udpSocket.isClosed()) {
                    try {
                        Enumeration<NetworkInterface> nis = NetworkInterface.getNetworkInterfaces();
                        while (nis != null && nis.hasMoreElements()) {
                            NetworkInterface ni = nis.nextElement();
                            if (!ni.isUp() || ni.isLoopback()) continue;
                            for (InterfaceAddress ia : ni.getInterfaceAddresses()) {
                                InetAddress addr = ia.getAddress();
                                if (!(addr instanceof Inet4Address)) continue;
                                byte[] ip = addr.getAddress();
                                if (ip.length != 4 || (ip[0] & 0xff) == 127 || (ip[0] & 0xff) == 169) continue;
                                int myLast = ip[3] & 0xff;
                                for (int h = 1; h <= 254; h++) {
                                    if (h == myLast) continue;
                                    ip[3] = (byte) h;
                                    InetAddress dst = InetAddress.getByAddress(ip);
                                    udpSocket.send(new DatagramPacket(ping, ping.length, dst, UDP_PORT));
                                }
                            }
                        }
                    } catch (Exception ignored) {}
                }
            }
        }).start();
    }

    private void pumpMultiplayerTxLocked(byte[] txBuf) {
        int len;
        while ((len = NativeVm.mpPopTx(txBuf)) > 0) {
            byte[] pkt = new byte[len + 4];
            pkt[0] = (byte) (localUid & 0xff);
            pkt[1] = (byte) ((localUid >> 8) & 0xff);
            pkt[2] = (byte) ((localUid >> 16) & 0xff);
            pkt[3] = (byte) ((localUid >> 24) & 0xff);
            System.arraycopy(txBuf, 0, pkt, 4, len);
            int cmd = txBuf[0] & 0xff;
            boolean isDiscoveryPkt = (cmd == 0xfe || cmd == 0xff);
            sendUdpPacketToPeers(pkt, isDiscoveryPkt);
        }
    }

    private void startEngineThreads() {
        runningThreads = true;

        // 1. UDP Auto-Discovery & Unicast Lockstep Multiplayer Thread (Port 18765)
        udpRxThread = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    udpSocket = new DatagramSocket(null);
                    udpSocket.setReuseAddress(true);
                    udpSocket.setBroadcast(true);
                    udpSocket.bind(new InetSocketAddress(UDP_PORT));
                    byte[] rxBuf = new byte[256];
                    byte[] txBuf = new byte[204];
                    while (runningThreads) {
                        DatagramPacket dp = new DatagramPacket(rxBuf, rxBuf.length);
                        udpSocket.receive(dp);
                        int rlen = dp.getLength();
                        if (rlen <= 4) continue;
                        int senderUid = (rxBuf[0] & 0xff) | ((rxBuf[1] & 0xff) << 8)
                            | ((rxBuf[2] & 0xff) << 16) | ((rxBuf[3] & 0xff) << 24);
                        if (senderUid == localUid || senderUid == 0) continue;

                        InetAddress peerAddr = dp.getAddress();
                        if (peerAddr != null) {
                            knownPeers.put(peerAddr, System.currentTimeMillis());
                        }

                        int b0 = rxBuf[4] & 0xff;
                        int b1 = (rlen > 5) ? (rxBuf[5] & 0xff) : 0;
                        if (b0 == 0xfd) {
                            // Auto-discovery heartbeat ping (0x01) -> reply with direct unicast pong (0x02)
                            if (b1 == 0x01 && peerAddr != null) {
                                byte[] pong = new byte[]{
                                    (byte) (localUid & 0xff),
                                    (byte) ((localUid >> 8) & 0xff),
                                    (byte) ((localUid >> 16) & 0xff),
                                    (byte) ((localUid >> 24) & 0xff),
                                    (byte) 0xfd,
                                    (byte) 0x02
                                };
                                try {
                                    udpSocket.send(new DatagramPacket(pong, pong.length, peerAddr, UDP_PORT));
                                } catch (Exception ignored) {}
                            }
                            continue;
                        }

                        if (!vmInitialized) continue;
                        int payLen = Math.min(rlen - 4, 200);
                        byte[] payload = new byte[payLen];
                        System.arraycopy(rxBuf, 4, payload, 0, payLen);
                        synchronized (NativeVm.VM_LOCK) {
                            NativeVm.mpPushRx(payload, payLen);
                            if (!paused && NativeVm.mpIsWaiting()) {
                                NativeVm.tick(33);
                                tickCounter++;
                                flushPendingKeyUpsLocked();
                                NativeVm.copyNativeRgba(directFrameBuf);
                                pumpMultiplayerTxLocked(txBuf);
                            }
                        }
                    }
                } catch (Exception ignored) {}
            }
        }, "ExplodeUDPThread");
        udpRxThread.setDaemon(true);
        udpRxThread.start();

        // 2. Native Simulation Thread (30/45/60 TPS)
        simThread = new Thread(new Runnable() {
            @Override
            public void run() {
                byte[] cfgBuf = new byte[104];
                byte[] txBuf = new byte[204];
                long fpsTimer = System.currentTimeMillis();
                int ticks = 0;
                while (runningThreads) {
                    long t0 = System.currentTimeMillis();
                    if (vmInitialized && !paused) {
                        synchronized (NativeVm.VM_LOCK) {
                            NativeVm.tick(33);
                            tickCounter++;
                            flushPendingKeyUpsLocked();
                            NativeVm.copyNativeRgba(directFrameBuf);
                            pumpMultiplayerTxLocked(txBuf);
                            if (NativeVm.consumeCfgDirty(cfgBuf)) {
                                prefs.edit().putString(
                                    "game_cfg_b64", Base64.encodeToString(cfgBuf, Base64.NO_WRAP)
                                ).apply();
                            }
                        }
                        ticks++;
                    }
                    long now = System.currentTimeMillis();
                    if ((ticks & 15) == 0) {
                        sendDiscoveryBeacon();
                    }
                    if (now - fpsTimer >= 1000) {
                        currentSimTps = ticks;
                        ticks = 0;
                        fpsTimer = now;
                        sendDiscoveryBeacon();
                        runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                int peers = knownPeers.size();
                                if (peers > 0) {
                                    tvTopLeft.setText("LAN READY (" + peers + " PEER)");
                                    tvTopLeft.setTextColor(Color.parseColor("#10b981"));
                                } else {
                                    tvTopLeft.setText("POWER ON");
                                    tvTopLeft.setTextColor(Color.parseColor("#6c6f78"));
                                }
                                int role = vmInitialized ? NativeVm.mpGetRole() : 0;
                                String mpTag = role == 1 ? " • HOST" : (role == 2 ? " • CLIENT" : "");
                                tvTopRight.setText(currentGlFps + " FPS GPU (" + currentSimTps + " TPS)" + mpTag);
                            }
                        });
                    }
                    long stepMs = Math.max(14, 1000 / Math.max(20, targetSimFps));
                    long elapsed = System.currentTimeMillis() - t0;
                    if (elapsed < stepMs) {
                        try { Thread.sleep(stepMs - elapsed); } catch (Exception ignored) {}
                    }
                }
            }
        }, "ExplodeSimThread");
        simThread.start();

        // 3. Native 16,000 Hz AudioTrack Thread
        audioThread = new Thread(new Runnable() {
            @Override
            public void run() {
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO);
                int minBuf = AudioTrack.getMinBufferSize(
                    16000, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT
                );
                AudioTrack track = new AudioTrack(
                    AudioManager.STREAM_MUSIC, 16000,
                    AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    Math.max(minBuf, 768 * 4), AudioTrack.MODE_STREAM
                );
                short[] pcm = new short[768];
                short[] silence = new short[768];
                track.play();
                while (runningThreads) {
                    if (!vmInitialized || paused || audioMuted) {
                        track.write(silence, 0, 768);
                    } else {
                        synchronized (NativeVm.VM_LOCK) {
                            NativeVm.mixAudio(pcm);
                        }
                        track.write(pcm, 0, 768);
                    }
                }
                track.stop();
                track.release();
            }
        }, "ExplodeAudioThread");
        audioThread.start();
    }

    private void showSpSettingsModal() {
        final String[] modes = {"Retro Pixel 1x", "xBR Crisp 4x (GPU)", "xBR+Anime4K 4x (GPU)"};
        final String[] items = {
            "Upscaler: " + modes[upscaleMode],
            "Target Speed: " + targetSimFps + " FPS",
            "Audio: " + (audioMuted ? "MUTE" : "ON"),
            "[Cheat] MAX POWERUPS (In-Game)",
            "[Cheat] GOD MODE (" + (godMode ? "ON" : "OFF") + ")",
            "[Cheat] IDRULEZ (Unlock All Stages)",
            "[Cheat] Cycle Secret Alien (ALIEN1..7)",
            "[Input] Open 0-9 Numpad (For Enter Name)",
            "[File]  Load Custom .SIS Package",
            "[Reset] Reboot Symbian S60 VM"
        };
        new AlertDialog.Builder(this)
            .setTitle("EXPLODE ARENA SP — NATIVE JNI MENU")
            .setItems(items, new DialogInterface.OnClickListener() {
                @Override
                public void onClick(DialogInterface dialog, int which) {
                    vibrateTick(10);
                    switch (which) {
                        case 0:
                            upscaleMode = (upscaleMode + 1) % 3;
                            Toast.makeText(MainActivity.this, "Upscaler: " + modes[upscaleMode], Toast.LENGTH_SHORT).show();
                            break;
                        case 1:
                            targetSimFps = (targetSimFps == 30) ? 45 : (targetSimFps == 45 ? 60 : (targetSimFps == 60 ? 20 : 30));
                            Toast.makeText(MainActivity.this, "Speed: " + targetSimFps + " FPS", Toast.LENGTH_SHORT).show();
                            break;
                        case 2:
                            audioMuted = !audioMuted;
                            break;
                        case 3:
                            synchronized (NativeVm.VM_LOCK) { NativeVm.applyCheat(20); }
                            Toast.makeText(MainActivity.this, "Activated MAX POWERUPS!", Toast.LENGTH_SHORT).show();
                            break;
                        case 4:
                            godMode = !godMode;
                            synchronized (NativeVm.VM_LOCK) { NativeVm.applyCheat(21); }
                            Toast.makeText(MainActivity.this, "God Mode: " + (godMode ? "ON" : "OFF"), Toast.LENGTH_SHORT).show();
                            break;
                        case 5:
                            synchronized (NativeVm.VM_LOCK) { NativeVm.applyCheat(1); }
                            Toast.makeText(MainActivity.this, "Unlocked All Stages (IDRULEZ)!", Toast.LENGTH_SHORT).show();
                            break;
                        case 6:
                            int c = alienCycle;
                            alienCycle = (alienCycle >= 10) ? 4 : (alienCycle + 1);
                            synchronized (NativeVm.VM_LOCK) { NativeVm.applyCheat(c); }
                            Toast.makeText(MainActivity.this, "Player 1 set to ALIEN" + (c - 3), Toast.LENGTH_SHORT).show();
                            break;
                        case 7:
                            showNumpadDialog();
                            break;
                        case 8:
                            promptPickSisFile();
                            break;
                        case 9:
                            if (cachedCodeBytes != null && cachedPakBytes != null) {
                                byte[] savedCfg = null;
                                String cfgB64 = prefs.getString("game_cfg_b64", null);
                                if (cfgB64 != null) {
                                    try { savedCfg = Base64.decode(cfgB64, Base64.DEFAULT); } catch (Exception ignored) {}
                                }
                                synchronized (NativeVm.VM_LOCK) {
                                    NativeVm.initVm(cachedCodeBytes, cachedPakBytes, savedCfg, localUid);
                                }
                            }
                            break;
                    }
                }
            })
            .setNegativeButton("Close", null)
            .show();
    }

    private void showNumpadDialog() {
        final String[] keys = {
            "1 (.,-;0)", "2 (ABC)", "3 (DEF)",
            "4 (GHI)", "5 (JKL)", "6 (MNO)",
            "7 (PQRS)", "8 (TUV)", "9 (WXYZ)",
            "0 (Space)", "CLEAR (Backspace)"
        };
        final int[] scans = {49, 50, 51, 52, 53, 54, 55, 56, 57, 48, 1};
        new AlertDialog.Builder(this)
            .setTitle("Nokia S60 Numpad (Name Entry)")
            .setItems(keys, new DialogInterface.OnClickListener() {
                @Override
                public void onClick(DialogInterface d, int idx) {
                    vibrateTick(8);
                    pulseVmKey(scans[idx]);
                }
            })
            .setNegativeButton("Done", null)
            .show();
    }

    // OpenGL ES 2.0 Hardware Renderer (De-Dither + 21-Tap xBR + Anime4K Fragment Shader)
    private class SpGlRenderer implements GLSurfaceView.Renderer {
        private int program;
        private int texId;
        private int modeLoc;
        private FloatBuffer quadBuf;
        private long fpsStart = System.currentTimeMillis();
        private int frames = 0;

        private static final String VS =
            "attribute vec2 a_pos;\n" +
            "varying vec2 v_uv;\n" +
            "void main() {\n" +
            "  v_uv = vec2(a_pos.x * 0.5 + 0.5, 0.5 - a_pos.y * 0.5);\n" +
            "  gl_Position = vec4(a_pos, 0.0, 1.0);\n" +
            "}\n";

        private static final String FS =
            "precision highp float;\n" +
            "varying vec2 v_uv;\n" +
            "uniform sampler2D u_tex;\n" +
            "uniform int u_mode;\n" +
            "const vec2 RES = vec2(176.0, 208.0);\n" +
            "const vec2 INV_RES = vec2(1.0 / 176.0, 1.0 / 208.0);\n" +
            "vec3 fetchPx(vec2 ip, float dx, float dy) {\n" +
            "  vec2 p = clamp(ip + vec2(dx, dy) + 0.5, vec2(0.5), RES - 0.5) * INV_RES;\n" +
            "  return texture2D(u_tex, p).rgb;\n" +
            "}\n" +
            "float luma(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }\n" +
            "float ydist(vec3 a, vec3 b) { vec3 d = abs(a - b); return d.r * 3.0 + d.g * 6.0 + d.b; }\n" +
            "void main() {\n" +
            "  vec2 pos = v_uv * RES;\n" +
            "  vec2 ip = floor(pos);\n" +
            "  vec2 fp = fract(pos);\n" +
            "  vec3 E = fetchPx(ip, 0.0, 0.0);\n" +
            "  if (u_mode == 0) { gl_FragColor = vec4(E, 1.0); return; }\n" +
            "  vec3 B = fetchPx(ip, 0.0, -1.0);\n" +
            "  vec3 D = fetchPx(ip, -1.0, 0.0);\n" +
            "  vec3 F = fetchPx(ip, 1.0, 0.0);\n" +
            "  vec3 H = fetchPx(ip, 0.0, 1.0);\n" +
            "  if (ydist(E, B) < 0.04 && ydist(E, D) < 0.04 && ydist(E, F) < 0.04 && ydist(E, H) < 0.04) {\n" +
            "    gl_FragColor = vec4(E, 1.0); return;\n" +
            "  }\n" +
            "  vec3 A = fetchPx(ip, -1.0, -1.0);\n" +
            "  vec3 C = fetchPx(ip, 1.0, -1.0);\n" +
            "  vec3 G = fetchPx(ip, -1.0, 1.0);\n" +
            "  vec3 I = fetchPx(ip, 1.0, 1.0);\n" +
            "  if (u_mode == 2) {\n" +
            "    vec3 sum = E * 2.5; float wsum = 2.5;\n" +
            "    float dB = ydist(E, B); if (dB < 0.45) { float w = 0.45 - dB; sum += B * w; wsum += w; }\n" +
            "    float dD = ydist(E, D); if (dD < 0.45) { float w = 0.45 - dD; sum += D * w; wsum += w; }\n" +
            "    float dF = ydist(E, F); if (dF < 0.45) { float w = 0.45 - dF; sum += F * w; wsum += w; }\n" +
            "    float dH = ydist(E, H); if (dH < 0.45) { float w = 0.45 - dH; sum += H * w; wsum += w; }\n" +
            "    E = sum / wsum;\n" +
            "  }\n" +
            "  vec3 B1 = fetchPx(ip, 0.0, -2.0);\n" +
            "  vec3 D0 = fetchPx(ip, -2.0, 0.0);\n" +
            "  vec3 F4 = fetchPx(ip, 2.0, 0.0);\n" +
            "  vec3 H5 = fetchPx(ip, 0.0, 2.0);\n" +
            "  vec3 res = E;\n" +
            "  if (fp.x >= 0.5 && fp.y >= 0.5) {\n" +
            "    float wd1 = ydist(E, C) + ydist(E, G) + ydist(I, H5) + ydist(I, F4) + 4.0 * ydist(H, F);\n" +
            "    float wd2 = ydist(H, D) + ydist(F, B) + 4.0 * ydist(E, I);\n" +
            "    if (wd1 < wd2) {\n" +
            "      vec3 nc = (ydist(E, F) <= ydist(E, H)) ? F : H;\n" +
            "      res = mix(E, nc, smoothstep(0.35, 1.05, (fp.x - 0.5) + (fp.y - 0.5)) * 0.78);\n" +
            "    }\n" +
            "  } else if (fp.x < 0.5 && fp.y >= 0.5) {\n" +
            "    float wd1 = ydist(E, A) + ydist(E, I) + ydist(G, H5) + ydist(G, D0) + 4.0 * ydist(D, H);\n" +
            "    float wd2 = ydist(H, F) + ydist(D, B) + 4.0 * ydist(E, G);\n" +
            "    if (wd1 < wd2) {\n" +
            "      vec3 nc = (ydist(E, D) <= ydist(E, H)) ? D : H;\n" +
            "      res = mix(E, nc, smoothstep(0.35, 1.05, (0.5 - fp.x) + (fp.y - 0.5)) * 0.78);\n" +
            "    }\n" +
            "  } else if (fp.x >= 0.5 && fp.y < 0.5) {\n" +
            "    float wd1 = ydist(E, A) + ydist(E, I) + ydist(C, B1) + ydist(C, F4) + 4.0 * ydist(B, F);\n" +
            "    float wd2 = ydist(B, D) + ydist(F, H) + 4.0 * ydist(E, C);\n" +
            "    if (wd1 < wd2) {\n" +
            "      vec3 nc = (ydist(E, F) <= ydist(E, B)) ? F : B;\n" +
            "      res = mix(E, nc, smoothstep(0.35, 1.05, (fp.x - 0.5) + (0.5 - fp.y)) * 0.78);\n" +
            "    }\n" +
            "  } else {\n" +
            "    float wd1 = ydist(E, G) + ydist(E, C) + ydist(A, B1) + ydist(A, D0) + 4.0 * ydist(D, B);\n" +
            "    float wd2 = ydist(B, F) + ydist(D, H) + 4.0 * ydist(E, A);\n" +
            "    if (wd1 < wd2) {\n" +
            "      vec3 nc = (ydist(E, D) <= ydist(E, B)) ? D : B;\n" +
            "      res = mix(E, nc, smoothstep(0.35, 1.05, (0.5 - fp.x) + (0.5 - fp.y)) * 0.78);\n" +
            "    }\n" +
            "  }\n" +
            "  if (u_mode == 2) {\n" +
            "    float lE = luma(res), lB = luma(B), lD = luma(D), lF = luma(F), lH = luma(H);\n" +
            "    if (lB > lE && lD > lE && fp.x < 0.5 && fp.y < 0.5) res = mix(res, 0.5 * (B + D), 0.35);\n" +
            "    if (lB > lE && lF > lE && fp.x >= 0.5 && fp.y < 0.5) res = mix(res, 0.5 * (B + F), 0.35);\n" +
            "    if (lH > lE && lD > lE && fp.x < 0.5 && fp.y >= 0.5) res = mix(res, 0.5 * (H + D), 0.35);\n" +
            "    if (lH > lE && lF > lE && fp.x >= 0.5 && fp.y >= 0.5) res = mix(res, 0.5 * (H + F), 0.35);\n" +
            "  }\n" +
            "  gl_FragColor = vec4(res, 1.0);\n" +
            "}\n";

        private int compileShader(int type, String src) {
            int s = GLES20.glCreateShader(type);
            GLES20.glShaderSource(s, src);
            GLES20.glCompileShader(s);
            return s;
        }

        @Override
        public void onSurfaceCreated(GL10 gl, EGLConfig config) {
            program = GLES20.glCreateProgram();
            GLES20.glAttachShader(program, compileShader(GLES20.GL_VERTEX_SHADER, VS));
            GLES20.glAttachShader(program, compileShader(GLES20.GL_FRAGMENT_SHADER, FS));
            GLES20.glLinkProgram(program);
            GLES20.glUseProgram(program);

            float[] verts = {-1f, -1f, 1f, -1f, -1f, 1f, -1f, 1f, 1f, -1f, 1f, 1f};
            quadBuf = ByteBuffer.allocateDirect(verts.length * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
            quadBuf.put(verts).position(0);

            int posLoc = GLES20.glGetAttribLocation(program, "a_pos");
            GLES20.glEnableVertexAttribArray(posLoc);
            GLES20.glVertexAttribPointer(posLoc, 2, GLES20.GL_FLOAT, false, 0, quadBuf);

            int[] tex = new int[1];
            GLES20.glGenTextures(1, tex, 0);
            texId = tex[0];
            GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texId);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_NEAREST);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_NEAREST);
            GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D, 0, GLES20.GL_RGBA, 176, 208, 0, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, null);

            modeLoc = GLES20.glGetUniformLocation(program, "u_mode");
        }

        @Override
        public void onSurfaceChanged(GL10 gl, int width, int height) {
            GLES20.glViewport(0, 0, width, height);
        }

        @Override
        public void onDrawFrame(GL10 gl) {
            GLES20.glUseProgram(program);
            GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texId);
            if (vmInitialized) {
                synchronized (NativeVm.VM_LOCK) {
                    directFrameBuf.position(0);
                    GLES20.glTexSubImage2D(
                        GLES20.GL_TEXTURE_2D, 0, 0, 0, 176, 208,
                        GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, directFrameBuf
                    );
                }
            }
            GLES20.glUniform1i(modeLoc, upscaleMode);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLES, 0, 6);

            frames++;
            long now = System.currentTimeMillis();
            if (now - fpsStart >= 1000) {
                currentGlFps = (int) ((frames * 1000L) / (now - fpsStart));
                frames = 0;
                fpsStart = now;
            }
        }
    }

    // Pure Native Android Canvas-Drawn GBA SP Lower Controller Deck with Multi-Touch & Slide D-Pad
    private class GbaSpDeckView extends View {
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF rect = new RectF();

        private float dpadCx, dpadCy, dpadWellR;
        private float bCx, bCy, aCx, aCy, abBtnR;
        private float gearCx, gearCy, smallBtnR;
        private float selectCx, selectCy, startCx, startCy;

        private int dpadPointerId = -1;
        private int activeDpadScan = 0;
        private final int[] pointerScans = new int[16];

        public GbaSpDeckView(Context ctx) {
            super(ctx);
        }

        @Override
        protected void onSizeChanged(int w, int h, int oldw, int oldh) {
            super.onSizeChanged(w, h, oldw, oldh);
            gearCx = w * 0.50f;
            gearCy = h * 0.12f;
            smallBtnR = Math.min(w, h) * 0.048f;

            dpadCx = w * 0.27f;
            dpadCy = h * 0.43f;
            dpadWellR = Math.min(w, h) * 0.23f;

            float abWellCx = w * 0.74f;
            float abWellCy = h * 0.41f;
            float sep = Math.min(w, h) * 0.105f;
            double ang = Math.toRadians(-24.0);
            bCx = abWellCx - (float) (Math.cos(ang) * sep);
            bCy = abWellCy - (float) (Math.sin(ang) * sep);
            aCx = abWellCx + (float) (Math.cos(ang) * sep);
            aCy = abWellCy + (float) (Math.sin(ang) * sep);
            abBtnR = Math.min(w, h) * 0.082f;

            selectCx = w * 0.405f;
            selectCy = h * 0.88f;
            startCx = w * 0.595f;
            startCy = h * 0.88f;
        }

        @Override
        protected void onDraw(Canvas c) {
            int w = getWidth(), h = getHeight();

            // 1. Lower Clamshell Matte Body
            rect.set(0, 0, w, h);
            p.setStyle(Paint.Style.FILL);
            p.setColor(Color.parseColor("#1c1c20"));
            c.drawRoundRect(rect, dp(28), dp(28), p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(2));
            p.setColor(Color.parseColor("#2b2b32"));
            c.drawRoundRect(rect, dp(28), dp(28), p);
            p.setStyle(Paint.Style.FILL);

            // 2. Right Edge Power LED
            p.setColor(Color.parseColor("#ff2a2a"));
            c.drawRoundRect(new RectF(w - dp(10), h * 0.18f, w - dp(1), h * 0.18f + dp(12)), dp(2), dp(2), p);
            p.setColor(Color.parseColor("#101014"));
            c.drawRoundRect(new RectF(w - dp(10), h * 0.24f, w - dp(1), h * 0.24f + dp(11)), dp(2), dp(2), p);

            // 3. Top-Center Gear / Brightness Button
            drawSmallRecessedButton(c, gearCx, gearCy, smallBtnR, "*", false);

            // 4. Left Circular Recessed Well + Classic '+' Cross D-Pad
            p.setColor(Color.parseColor("#131317"));
            c.drawCircle(dpadCx, dpadCy, dpadWellR, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(1.5f));
            p.setColor(Color.parseColor("#27272e"));
            c.drawCircle(dpadCx, dpadCy, dpadWellR, p);
            p.setStyle(Paint.Style.FILL);

            float armLen = dpadWellR * 0.72f;
            float armHalfW = dpadWellR * 0.25f;
            p.setColor(Color.parseColor("#44464c"));
            // Horizontal bar
            c.drawRoundRect(new RectF(dpadCx - armLen, dpadCy - armHalfW, dpadCx + armLen, dpadCy + armHalfW), dp(5), dp(5), p);
            // Vertical bar
            c.drawRoundRect(new RectF(dpadCx - armHalfW, dpadCy - armLen, dpadCx + armHalfW, dpadCy + armLen), dp(5), dp(5), p);

            // Highlight active D-Pad direction
            if (activeDpadScan != 0) {
                p.setColor(Color.argb(120, 245, 158, 11));
                if (activeDpadScan == 16) {
                    c.drawRoundRect(new RectF(dpadCx - armHalfW, dpadCy - armLen, dpadCx + armHalfW, dpadCy - armHalfW * 0.5f), dp(5), dp(5), p);
                } else if (activeDpadScan == 17) {
                    c.drawRoundRect(new RectF(dpadCx - armHalfW, dpadCy + armHalfW * 0.5f, dpadCx + armHalfW, dpadCy + armLen), dp(5), dp(5), p);
                } else if (activeDpadScan == 14) {
                    c.drawRoundRect(new RectF(dpadCx - armLen, dpadCy - armHalfW, dpadCx - armHalfW * 0.5f, dpadCy + armHalfW), dp(5), dp(5), p);
                } else if (activeDpadScan == 15) {
                    c.drawRoundRect(new RectF(dpadCx + armHalfW * 0.5f, dpadCy - armHalfW, dpadCx + armLen, dpadCy + armHalfW), dp(5), dp(5), p);
                }
            }

            // Center concave dimple
            p.setColor(Color.parseColor("#383a40"));
            c.drawCircle(dpadCx, dpadCy, armHalfW * 0.65f, p);

            // 5. Right Angled Pill Well + B & A Circular Buttons
            c.save();
            float abMidX = (bCx + aCx) * 0.5f;
            float abMidY = (bCy + aCy) * 0.5f;
            c.rotate(-24f, abMidX, abMidY);
            float pillW = (float) Math.hypot(aCx - bCx, aCy - bCy) * 0.5f + abBtnR * 1.38f;
            float pillH = abBtnR * 1.35f;
            p.setColor(Color.parseColor("#131317"));
            c.drawRoundRect(new RectF(abMidX - pillW, abMidY - pillH, abMidX + pillW, abMidY + pillH), pillH, pillH, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(1.5f));
            p.setColor(Color.parseColor("#27272e"));
            c.drawRoundRect(new RectF(abMidX - pillW, abMidY - pillH, abMidX + pillW, abMidY + pillH), pillH, pillH, p);
            p.setStyle(Paint.Style.FILL);
            c.restore();

            drawAbButton(c, bCx, bCy, abBtnR, "B", isScanActive(200));
            drawAbButton(c, aCx, aCy, abBtnR, "A", isScanActive(201));

            // 6. Center 4x4 Speaker Grille Dots
            float gridStartX = w * 0.50f - dp(21);
            float gridStartY = h * 0.64f;
            p.setColor(Color.parseColor("#08080a"));
            for (int r = 0; r < 4; r++) {
                for (int col = 0; col < 4; col++) {
                    c.drawCircle(gridStartX + col * dp(14), gridStartY + r * dp(12), dp(3.2f), p);
                }
            }

            // 7. Bottom-Center SELECT (164) & START (165) Buttons
            drawSmallRecessedButton(c, selectCx, selectCy, smallBtnR, null, isScanActive(164));
            drawSmallRecessedButton(c, startCx, startCy, smallBtnR, null, isScanActive(165));
            p.setColor(Color.parseColor("#6c6f78"));
            p.setTextSize(dp(9.5f));
            p.setTextAlign(Paint.Align.CENTER);
            p.setTypeface(Typeface.DEFAULT_BOLD);
            c.drawText("SELECT", selectCx, selectCy + smallBtnR * 2.15f, p);
            c.drawText("START", startCx, startCy + smallBtnR * 2.15f, p);
        }

        private boolean isScanActive(int scan) {
            for (int s : pointerScans) {
                if (s == scan) return true;
            }
            return false;
        }

        private void drawSmallRecessedButton(Canvas c, float cx, float cy, float r, String label, boolean active) {
            p.setColor(Color.parseColor("#111115"));
            c.drawCircle(cx, cy, r * 1.45f, p);
            p.setColor(active ? Color.parseColor("#f59e0b") : Color.parseColor("#474950"));
            c.drawCircle(cx, cy, r, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(1.5f));
            p.setColor(Color.parseColor("#6c6f78"));
            c.drawCircle(cx, cy, r, p);
            p.setStyle(Paint.Style.FILL);
            if (label != null) {
                p.setColor(Color.parseColor("#1c1c20"));
                p.setTextSize(r * 1.05f);
                p.setTextAlign(Paint.Align.CENTER);
                p.setTypeface(Typeface.DEFAULT_BOLD);
                c.drawText(label, cx, cy + r * 0.36f, p);
            }
        }

        private void drawAbButton(Canvas c, float cx, float cy, float r, String label, boolean active) {
            p.setShader(new RadialGradient(
                cx - r * 0.3f, cy - r * 0.3f, r * 1.3f,
                active ? Color.parseColor("#fbbf24") : Color.parseColor("#5a5d66"),
                active ? Color.parseColor("#b45309") : Color.parseColor("#33353b"),
                Shader.TileMode.CLAMP
            ));
            c.drawCircle(cx, cy, r, p);
            p.setShader(null);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(1.5f));
            p.setColor(active ? Color.WHITE : Color.parseColor("#757882"));
            c.drawCircle(cx, cy, r, p);
            p.setStyle(Paint.Style.FILL);

            p.setColor(active ? Color.parseColor("#111115") : Color.parseColor("#232429"));
            p.setTextSize(r * 0.95f);
            p.setTextAlign(Paint.Align.CENTER);
            p.setTypeface(Typeface.DEFAULT_BOLD);
            c.drawText(label, cx, cy + r * 0.34f, p);
        }

        private int hitTestActionScan(float x, float y) {
            if (Math.hypot(x - bCx, y - bCy) <= abBtnR * 1.35f) return 200; // B
            if (Math.hypot(x - aCx, y - aCy) <= abBtnR * 1.35f) return 201; // A
            if (Math.hypot(x - selectCx, y - selectCy) <= smallBtnR * 1.9f) return 164; // SELECT (Soft L)
            if (Math.hypot(x - startCx, y - startCy) <= smallBtnR * 1.9f) return 165; // START (Soft R)
            return 0;
        }

        private void updateDpadFromPoint(float x, float y) {
            float dx = x - dpadCx;
            float dy = y - dpadCy;
            float dist = (float) Math.hypot(dx, dy);
            if (dist < dpadWellR * 0.16f) {
                if (activeDpadScan != 0) {
                    sendVmKey(activeDpadScan, false);
                    activeDpadScan = 0;
                    invalidate();
                }
                return;
            }
            int next = (Math.abs(dx) > Math.abs(dy)) ? (dx > 0 ? 15 : 14) : (dy > 0 ? 17 : 16);
            if (next != activeDpadScan) {
                if (activeDpadScan != 0) {
                    synchronized (NativeVm.VM_LOCK) {
                        pendingKeyUp[activeDpadScan] = false;
                        keyIsDown[activeDpadScan] = false;
                        NativeVm.keyEvent(activeDpadScan, 0);
                    }
                }
                activeDpadScan = next;
                sendVmKey(activeDpadScan, true);
                vibrateTick(6);
                invalidate();
            }
        }

        @Override
        public boolean onTouchEvent(MotionEvent ev) {
            int action = ev.getActionMasked();
            int idx = ev.getActionIndex();
            int pid = ev.getPointerId(idx);
            float x = ev.getX(idx);
            float y = ev.getY(idx);

            switch (action) {
                case MotionEvent.ACTION_DOWN:
                case MotionEvent.ACTION_POINTER_DOWN: {
                    if (Math.hypot(x - gearCx, y - gearCy) <= smallBtnR * 2.0f) {
                        vibrateTick(10);
                        showSpSettingsModal();
                        return true;
                    }
                    if (dpadPointerId == -1 && Math.hypot(x - dpadCx, y - dpadCy) <= dpadWellR * 1.25f) {
                        dpadPointerId = pid;
                        updateDpadFromPoint(x, y);
                        return true;
                    }
                    int scan = hitTestActionScan(x, y);
                    if (scan != 0 && pid < pointerScans.length) {
                        pointerScans[pid] = scan;
                        vibrateTick(9);
                        sendVmKey(scan, true);
                        invalidate();
                    }
                    break;
                }
                case MotionEvent.ACTION_MOVE: {
                    for (int i = 0; i < ev.getPointerCount(); i++) {
                        int id = ev.getPointerId(i);
                        float px = ev.getX(i), py = ev.getY(i);
                        if (id == dpadPointerId) {
                            updateDpadFromPoint(px, py);
                        } else if (id < pointerScans.length) {
                            int prev = pointerScans[id];
                            int next = hitTestActionScan(px, py);
                            if (prev != next) {
                                if (prev != 0) sendVmKey(prev, false);
                                if (next != 0) {
                                    vibrateTick(8);
                                    sendVmKey(next, true);
                                }
                                pointerScans[id] = next;
                                invalidate();
                            }
                        }
                    }
                    break;
                }
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_POINTER_UP:
                case MotionEvent.ACTION_CANCEL: {
                    if (pid == dpadPointerId || action == MotionEvent.ACTION_CANCEL) {
                        dpadPointerId = -1;
                        if (activeDpadScan != 0) {
                            sendVmKey(activeDpadScan, false);
                            activeDpadScan = 0;
                            invalidate();
                        }
                    }
                    if (pid < pointerScans.length && pointerScans[pid] != 0) {
                        sendVmKey(pointerScans[pid], false);
                        pointerScans[pid] = 0;
                        invalidate();
                    }
                    break;
                }
            }
            return true;
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            vibrateTick(8);
            pulseVmKey(165); // Right Softkey (Pause / Proceed / Back)
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onPause() {
        super.onPause();
        paused = true;
        if (glView != null) glView.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        paused = false;
        applyImmersive();
        if (glView != null) glView.onResume();
    }

    @Override
    protected void onDestroy() {
        runningThreads = false;
        if (udpSocket != null) udpSocket.close();
        if (multicastLock != null && multicastLock.isHeld()) {
            try { multicastLock.release(); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }
}
"""
with open(f"{WORK}/src/im/agusibrah/explodearena/jni/MainActivity.java", "w") as f:
    f.write(main_java)

# 7. Compile resources with aapt2 (-0 .sis so game.sis is stored uncompressed)
subprocess.run([f"{BUILD_TOOLS}/aapt2", "compile", "--dir", f"{WORK}/res", "-o", f"{WORK}/res.zip"], check=True)
subprocess.run([
    f"{BUILD_TOOLS}/aapt2", "link",
    "-I", ANDROID_JAR,
    "--manifest", f"{WORK}/AndroidManifest.xml",
    "--java", f"{WORK}/src",
    "-A", f"{WORK}/assets",
    "-0", ".sis",
    "-o", f"{WORK}/unaligned.apk",
    f"{WORK}/res.zip"
], check=True)

# 8. Compile Java -> DEX with javac + d8
java_files = [
    f"{WORK}/src/im/agusibrah/explodearena/jni/NativeVm.java",
    f"{WORK}/src/im/agusibrah/explodearena/jni/MainActivity.java",
    f"{WORK}/src/im/agusibrah/explodearena/jni/R.java"
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

# 9. Package classes.dex + lib/arm64-v8a/libexplodevm.so + lib/armeabi-v7a/libexplodevm.so into APK
subprocess.run(["zip", "-j", f"{WORK}/unaligned.apk", f"{WORK}/classes.dex"], check=True)
subprocess.run(["zip", "-r", f"{WORK}/unaligned.apk", "lib"], cwd=WORK, check=True)

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

subprocess.run([f"{BUILD_TOOLS}/apksigner", "verify", "-v", out_apk], check=True)
print(f"SUCCESS: Built Native JNI + OpenGL ES APK -> {out_apk} ({os.path.getsize(out_apk):,} bytes)")
