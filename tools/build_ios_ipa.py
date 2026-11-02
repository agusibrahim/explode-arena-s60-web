#!/usr/bin/env python3
"""
Explode Arena (Symbian S60) — iOS .IPA Builder (Unsigned / Ad-Hoc for Sideloadly, AltStore, TrollStore)

Builds TWO iOS .IPA packages:
  1. ExplodeArena-S60-Native-iOS.ipa:
     100% Pure Native Objective-C + C (`src/vm.c` compiled to arm64 Mach-O) +
     CoreGraphics/QuartzCore CALayer + AudioToolbox 16kHz AudioQueue +
     UIImpactFeedbackGenerator Taptic Engine + POSIX UDP Socket (Port 18765)
     Zero-Config LAN/Hotspot Auto-Discovery (compatible with iOS <-> iOS and iOS <-> Android JNI!).
  2. ExplodeArena-S60-WebView-iOS.ipa:
     WKWebView Edition with WebGL GPU 4x xBR+Anime4K Shader + GBA SP Clamshell UI +
     WebRTC P2P Room Code & LAN WebSocket.

Usage:
  python3 tools/build_ios_ipa.py [/path/to/Explode_Arena.sis]
"""

import os
import sys
import shutil
import base64
import struct
import zlib
import subprocess

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sis_input = sys.argv[1] if len(sys.argv) > 1 else None
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "/Users/macbook/Downloads"

SDK_PATH = subprocess.check_output(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"], text=True).strip().splitlines()[-1]
CLANG = subprocess.check_output(["xcrun", "--sdk", "iphoneos", "-f", "clang"], text=True).strip().splitlines()[-1]

def make_icon_png(path, W=180, H=180):
    raw = bytearray()
    cx, cy = W * 0.48, H * 0.56
    r = W * 0.32
    for y in range(H):
        raw.append(0)
        for x in range(W):
            bg_r = int(18 + (H - y) * 0.08)
            bg_g = int(22 + (H - y) * 0.10)
            bg_b = int(32 + (H - y) * 0.14)
            sd = ((x - W*0.69)**2 + (y - H*0.24)**2) ** 0.5
            if sd < W*0.14:
                t = 1.0 - sd / (W*0.14)
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

def build_native_ios_ipa():
    work = "/tmp/explode_ios_native_build"
    if os.path.exists(work):
        shutil.rmtree(work)
    app_dir = os.path.join(work, "Payload", "ExplodeArenaSP.app")
    os.makedirs(app_dir, exist_ok=True)

    make_icon_png(os.path.join(app_dir, "AppIcon60x60@2x.png"), 120, 120)
    make_icon_png(os.path.join(app_dir, "AppIcon60x60@3x.png"), 180, 180)
    make_icon_png(os.path.join(app_dir, "Icon.png"), 180, 180)

    if sis_input and os.path.isfile(sis_input):
        shutil.copy(sis_input, os.path.join(app_dir, "game.sis"))

    info_plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>Explode Arena SP</string>
    <key>CFBundleExecutable</key>
    <string>ExplodeArenaSP</string>
    <key>CFBundleIdentifier</key>
    <string>im.agusibrah.explodearena.ios.native</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ExplodeArenaSP</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleVersion</key>
    <string>2</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>MinimumOSVersion</key>
    <string>14.0</string>
    <key>UIDeviceFamily</key>
    <array>
        <integer>1</integer>
        <integer>2</integer>
    </array>
    <key>UILaunchScreen</key>
    <dict/>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>arm64</string>
    </array>
    <key>UIStatusBarHidden</key>
    <true/>
    <key>UIViewControllerBasedStatusBarAppearance</key>
    <false/>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
    </array>
    <key>CFBundleIcons</key>
    <dict>
        <key>CFBundlePrimaryIcon</key>
        <dict>
            <key>CFBundleIconFiles</key>
            <array>
                <string>AppIcon60x60</string>
                <string>Icon.png</string>
            </array>
        </dict>
    </dict>
    <key>NSLocalNetworkUsageDescription</key>
    <string>Explode Arena SP uses the local Wi-Fi or Hotspot network to automatically discover nearby players for multiplayer matches.</string>
</dict>
</plist>
"""
    with open(os.path.join(app_dir, "Info.plist"), "w") as f:
        f.write(info_plist)

    objc_src = r"""
#import <UIKit/UIKit.h>
#import <QuartzCore/QuartzCore.h>
#import <AudioToolbox/AudioToolbox.h>
#import <AVFoundation/AVFoundation.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <fcntl.h>
#include <unistd.h>
#include <zlib.h>

// External functions from src/vm.c
extern uint8_t *vm_get_code_buf(void);
extern uint8_t *vm_get_pak_buf(void);
extern uint8_t *vm_get_cfg_buf(void);
extern uint32_t vm_get_cfg_size(void);
extern uint32_t vm_consume_cfg_dirty(void);
extern uint32_t *vm_get_rgba_ptr(void);
extern uint32_t *vm_get_upscaled_rgba_ptr(void);
extern void vm_set_upscale_mode(uint32_t mode);
extern int16_t *vm_get_pcm_ptr(void);
extern void vm_init(uint32_t pak_len, uint32_t cfg_len);
extern void vm_tick(uint32_t dt_ms);
extern void vm_key_event(uint32_t scan_code, uint32_t pressed);
extern void vm_mix_audio(void);
extern void vm_apply_cheat(uint32_t cheat_id);
extern void vm_mp_set_local_uid(uint32_t uid);
extern uint32_t vm_mp_get_role(void);
extern uint32_t vm_mp_get_state(void);
extern uint32_t vm_mp_is_waiting(void);
extern uint32_t vm_mp_pop_tx(uint8_t *out_buf);
extern void vm_mp_push_rx(const uint8_t *pkt_data, uint32_t len);

#define UDP_PORT 18765
#define MAX_PEERS 8

static pthread_mutex_t g_vm_mutex = PTHREAD_MUTEX_INITIALIZER;
static int g_vm_ready = 0;
static int g_paused = 0;
static int g_audio_muted = 0;
static int g_god_mode = 0;
static int g_upscale_mode = 1; // 0 = Fast 1x Nearest, 1 = 4x xBR Crisp, 2 = 4x xBR+Anime4K
static int g_target_fps = 30;
static int g_alien_cycle = 4;
static uint32_t g_local_uid = 0;

static uint32_t g_tick_counter = 0;
static uint32_t g_keydown_tick[256];
static uint8_t  g_key_is_down[256];
static uint8_t  g_pending_keyup[256];

static int g_udp_sock = -1;
static struct in_addr g_peer_addrs[MAX_PEERS];
static double g_peer_last_seen[MAX_PEERS];
static int g_peer_count = 0;

static void send_vm_key(int scan, int pressed) {
    if (!g_vm_ready) return;
    int idx = scan & 0xff;
    pthread_mutex_lock(&g_vm_mutex);
    if (pressed) {
        g_pending_keyup[idx] = 0;
        g_keydown_tick[idx] = g_tick_counter;
        g_key_is_down[idx] = 1;
        vm_key_event((uint32_t)scan, 1);
    } else {
        if (g_key_is_down[idx] && (g_tick_counter - g_keydown_tick[idx]) < 2u) {
            g_pending_keyup[idx] = 1;
        } else {
            g_key_is_down[idx] = 0;
            g_pending_keyup[idx] = 0;
            vm_key_event((uint32_t)scan, 0);
        }
    }
    pthread_mutex_unlock(&g_vm_mutex);
}

static void pulse_vm_key(int scan) {
    send_vm_key(scan, 1);
    send_vm_key(scan, 0);
}

static void flush_pending_keyups_locked(void) {
    for (int s = 0; s < 256; s++) {
        if (g_pending_keyup[s] && (g_tick_counter - g_keydown_tick[s]) >= 2u) {
            g_pending_keyup[s] = 0;
            g_key_is_down[s] = 0;
            vm_key_event((uint32_t)s, 0);
        }
    }
}

// UDP Zero-Config Auto-Discovery & Unicast Lockstep Transport (Port 18765)
static void udp_init_socket(void) {
    g_udp_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (g_udp_sock < 0) return;
    int yes = 1;
    setsockopt(g_udp_sock, SOL_SOCKET, SO_BROADCAST, &yes, sizeof(yes));
    setsockopt(g_udp_sock, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    setsockopt(g_udp_sock, SOL_SOCKET, SO_REUSEPORT, &yes, sizeof(yes));
    int flags = fcntl(g_udp_sock, F_GETFL, 0);
    fcntl(g_udp_sock, F_SETFL, flags | O_NONBLOCK);

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(UDP_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    bind(g_udp_sock, (struct sockaddr *)&addr, sizeof(addr));
}

static void udp_send_to_addr(struct in_addr dst, const uint8_t *buf, size_t len) {
    if (g_udp_sock < 0) return;
    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port = htons(UDP_PORT);
    sa.sin_addr = dst;
    sendto(g_udp_sock, buf, len, 0, (struct sockaddr *)&sa, sizeof(sa));
}

static void udp_broadcast_packet(const uint8_t *pkt, size_t len, int also_bcast) {
    if (g_udp_sock < 0) return;
    double now = CFAbsoluteTimeGetCurrent();
    int sent_unicast = 0;
    for (int i = 0; i < g_peer_count; i++) {
        if (now - g_peer_last_seen[i] <= 15.0) {
            udp_send_to_addr(g_peer_addrs[i], pkt, len);
            sent_unicast++;
        }
    }
    if (!also_bcast && sent_unicast > 0) return;

    struct ifaddrs *ifap = NULL;
    if (getifaddrs(&ifap) == 0) {
        for (struct ifaddrs *ifa = ifap; ifa != NULL; ifa = ifa->ifa_next) {
            if (!ifa->ifa_addr || ifa->ifa_addr->sa_family != AF_INET) continue;
            if (!(ifa->ifa_flags & IFF_UP) || (ifa->ifa_flags & IFF_LOOPBACK)) continue;
            struct sockaddr_in *sin = (struct sockaddr_in *)ifa->ifa_addr;
            uint32_t ip_h = ntohl(sin->sin_addr.s_addr);
            if ((ip_h >> 24) == 127 || (ip_h >> 24) == 169) continue;

            if ((ifa->ifa_flags & IFF_BROADCAST) && ifa->ifa_dstaddr) {
                struct sockaddr_in *bcast = (struct sockaddr_in *)ifa->ifa_dstaddr;
                udp_send_to_addr(bcast->sin_addr, pkt, len);
            }
            // Unicast /24 subnet sweep (1..254) so Sideloadly iOS apps without Apple's restricted
            // multicast entitlement still auto-discover Android & iOS peers on Wi-Fi / Hotspot!
            uint32_t net_prefix = ip_h & 0xffffff00u;
            uint32_t my_last = ip_h & 0xffu;
            for (uint32_t host = 1; host <= 254; host++) {
                if (host == my_last) continue;
                struct in_addr target;
                target.s_addr = htonl(net_prefix | host);
                udp_send_to_addr(target, pkt, len);
            }
        }
        freeifaddrs(ifap);
    }
}

static void udp_send_heartbeat(void) {
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        uint8_t ping[6] = {
            (uint8_t)(g_local_uid & 0xff),
            (uint8_t)((g_local_uid >> 8) & 0xff),
            (uint8_t)((g_local_uid >> 16) & 0xff),
            (uint8_t)((g_local_uid >> 24) & 0xff),
            0xfd, 0x01
        };
        udp_broadcast_packet(ping, 6, 1);
    });
}

static void udp_pump_tx_locked(void) {
    uint8_t slot[204];
    while (vm_mp_pop_tx(slot)) {
        uint8_t len = slot[1];
        if (len > 200) len = 200;
        uint8_t pkt[208];
        pkt[0] = (uint8_t)(g_local_uid & 0xff);
        pkt[1] = (uint8_t)((g_local_uid >> 8) & 0xff);
        pkt[2] = (uint8_t)((g_local_uid >> 16) & 0xff);
        pkt[3] = (uint8_t)((g_local_uid >> 24) & 0xff);
        memcpy(pkt + 4, slot + 2, len);
        int cmd = slot[2];
        udp_broadcast_packet(pkt, 4 + len, (cmd == 0xfe || cmd == 0xff));
    }
}

static void udp_poll_rx(void) {
    if (g_udp_sock < 0) return;
    uint8_t rx[256];
    struct sockaddr_in src_sa;
    socklen_t slen = sizeof(src_sa);
    while (1) {
        ssize_t n = recvfrom(g_udp_sock, rx, sizeof(rx), 0, (struct sockaddr *)&src_sa, &slen);
        if (n <= 4) break;
        uint32_t sender_uid = (uint32_t)rx[0] | ((uint32_t)rx[1] << 8) | ((uint32_t)rx[2] << 16) | ((uint32_t)rx[3] << 24);
        if (sender_uid == g_local_uid || sender_uid == 0) continue;

        double now = CFAbsoluteTimeGetCurrent();
        int found = -1;
        for (int i = 0; i < g_peer_count; i++) {
            if (g_peer_addrs[i].s_addr == src_sa.sin_addr.s_addr) {
                found = i;
                break;
            }
        }
        if (found < 0 && g_peer_count < MAX_PEERS) {
            found = g_peer_count++;
            g_peer_addrs[found] = src_sa.sin_addr;
        }
        if (found >= 0) g_peer_last_seen[found] = now;

        if (rx[4] == 0xfd) {
            if (n > 5 && rx[5] == 0x01) {
                uint8_t pong[6] = {
                    (uint8_t)(g_local_uid & 0xff),
                    (uint8_t)((g_local_uid >> 8) & 0xff),
                    (uint8_t)((g_local_uid >> 16) & 0xff),
                    (uint8_t)((g_local_uid >> 24) & 0xff),
                    0xfd, 0x02
                };
                udp_send_to_addr(src_sa.sin_addr, pong, 6);
            }
            continue;
        }
        if (!g_vm_ready) continue;
        uint32_t pay_len = (uint32_t)(n - 4);
        if (pay_len > 200u) pay_len = 200u;
        pthread_mutex_lock(&g_vm_mutex);
        vm_mp_push_rx(rx + 4, pay_len);
        if (!g_paused && vm_mp_is_waiting()) {
            vm_tick(33);
            g_tick_counter++;
            flush_pending_keyups_locked();
            udp_pump_tx_locked();
        }
        pthread_mutex_unlock(&g_vm_mutex);
    }
}

// Native iOS AudioQueue (16,000 Hz 16-bit Mono PCM)
static AudioQueueRef g_aq = NULL;
static AudioQueueBufferRef g_aq_bufs[3];

static void aq_callback(void *userData, AudioQueueRef inAQ, AudioQueueBufferRef inBuf) {
    (void)userData;
    int16_t *dst = (int16_t *)inBuf->mAudioData;
    if (!g_vm_ready || g_paused || g_audio_muted) {
        memset(dst, 0, 768 * 2);
    } else {
        pthread_mutex_lock(&g_vm_mutex);
        vm_mix_audio();
        memcpy(dst, vm_get_pcm_ptr(), 768 * 2);
        pthread_mutex_unlock(&g_vm_mutex);
    }
    inBuf->mAudioDataByteSize = 768 * 2;
    AudioQueueEnqueueBuffer(inAQ, inBuf, 0, NULL);
}

static void start_ios_audio(void) {
    AVAudioSession *sess = [AVAudioSession sharedInstance];
    [sess setCategory:AVAudioSessionCategoryPlayback withOptions:AVAudioSessionCategoryOptionMixWithOthers error:nil];
    [sess setActive:YES error:nil];

    AudioStreamBasicDescription fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.mSampleRate = 16000.0;
    fmt.mFormatID = kAudioFormatLinearPCM;
    fmt.mFormatFlags = kLinearPCMFormatFlagIsSignedInteger | kLinearPCMFormatFlagIsPacked;
    fmt.mFramesPerPacket = 1;
    fmt.mChannelsPerFrame = 1;
    fmt.mBitsPerChannel = 16;
    fmt.mBytesPerPacket = 2;
    fmt.mBytesPerFrame = 2;

    if (AudioQueueNewOutput(&fmt, aq_callback, NULL, NULL, kCFRunLoopCommonModes, 0, &g_aq) == noErr) {
        for (int i = 0; i < 3; i++) {
            AudioQueueAllocateBuffer(g_aq, 768 * 2, &g_aq_bufs[i]);
            memset(g_aq_bufs[i]->mAudioData, 0, 768 * 2);
            g_aq_bufs[i]->mAudioDataByteSize = 768 * 2;
            AudioQueueEnqueueBuffer(g_aq, g_aq_bufs[i], 0, NULL);
        }
        AudioQueueStart(g_aq, NULL);
    }
}

// Unpack Symbian EPOC R6 .sis in C using libz
static int boot_from_sis_data(const uint8_t *sis, size_t sis_len) {
    if (sis_len < 0x68) return 0;
    uint32_t uid3;
    memcpy(&uid3, sis + 0x08, 4);
    if (uid3 != 0x10000419u) return 0;

    uint16_t nfiles;
    uint32_t pfiles;
    memcpy(&nfiles, sis + 0x14, 2);
    memcpy(&pfiles, sis + 0x34, 4);

    int got_pak = 0, got_code = 0;
    for (uint16_t i = 0; i < nfiles; i++) {
        uint32_t off = pfiles + (uint32_t)i * 0x30u;
        if (off + 0x28u > sis_len) break;
        uint32_t fnLen, fnPtr, fLen, fPtr, uLen;
        memcpy(&fnLen, sis + off + 0x14, 4);
        memcpy(&fnPtr, sis + off + 0x18, 4);
        memcpy(&fLen,  sis + off + 0x1c, 4);
        memcpy(&fPtr,  sis + off + 0x20, 4);
        memcpy(&uLen,  sis + off + 0x24, 4);

        char name[128];
        int ni = 0;
        if (fnPtr + fnLen <= sis_len) {
            for (uint32_t k = 0; k < fnLen && ni < 126; k += 2) {
                char c = (char)sis[fnPtr + k];
                if (c >= 'A' && c <= 'Z') c += 32;
                name[ni++] = c;
            }
        }
        name[ni] = '\0';

        if (fPtr > 0 && fLen > 0 && fPtr + fLen <= sis_len && uLen > 0 && uLen < 600000u) {
            uint8_t *raw = (uint8_t *)malloc(uLen);
            if (!raw) continue;
            uLongf destLen = uLen;
            int ok = (fLen == uLen) ? (memcpy(raw, sis + fPtr, uLen), Z_OK) : uncompress(raw, &destLen, sis + fPtr, fLen);
            if (ok == Z_OK) {
                if (strstr(name, "data.pak")) {
                    memcpy(vm_get_pak_buf(), raw, uLen);
                    got_pak = (int)uLen;
                } else if (strstr(name, ".app") && uLen > 0x7cu) {
                    uint32_t codeSz, codeOff;
                    memcpy(&codeSz,  raw + 0x30, 4);
                    memcpy(&codeOff, raw + 0x64, 4);
                    if (codeOff > 0 && codeSz > 0 && codeOff + codeSz <= uLen) {
                        memcpy(vm_get_code_buf(), raw + codeOff, codeSz);
                        got_code = (int)codeSz;
                    }
                }
            }
            free(raw);
        }
    }

    if (!got_pak || !got_code) return 0;

    NSData *savedCfg = [[NSUserDefaults standardUserDefaults] dataForKey:@"game_cfg_104"];
    uint32_t cfgLen = 0;
    if (savedCfg && savedCfg.length == 0x68) {
        memcpy(vm_get_cfg_buf(), savedCfg.bytes, 0x68);
        cfgLen = 0x68;
    }

    pthread_mutex_lock(&g_vm_mutex);
    vm_mp_set_local_uid(g_local_uid);
    vm_init((uint32_t)got_pak, cfgLen);
    vm_set_upscale_mode((uint32_t)g_upscale_mode);
    g_vm_ready = 1;
    pthread_mutex_unlock(&g_vm_mutex);
    return 1;
}

@class SpMainViewController;

// Pure Native CoreGraphics GBA SP Lower Controller View
@interface GbaSpControllerView : UIView
@property (nonatomic, weak) SpMainViewController *ownerVc;
@end

@interface SpMainViewController : UIViewController
- (void)showSettingsSheet;
@end

@implementation GbaSpControllerView {
    CGFloat _dpadCx, _dpadCy, _dpadWellR;
    CGFloat _bCx, _bCy, _aCx, _aCy, _abBtnR;
    CGFloat _gearCx, _gearCy, _smallBtnR;
    CGFloat _selectCx, _selectCy, _startCx, _startCy;
    UITouch *_dpadTouch;
    int _activeDpadScan;
    NSMapTable<UITouch *, NSNumber *> *_actionTouches;
    UIImpactFeedbackGenerator *_hapticLight;
    UIImpactFeedbackGenerator *_hapticMed;
}

- (instancetype)initWithFrame:(CGRect)frame {
    if ((self = [super initWithFrame:frame])) {
        self.multipleTouchEnabled = YES;
        self.backgroundColor = [UIColor clearColor];
        _actionTouches = [NSMapTable weakToStrongObjectsMapTable];
        _hapticLight = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
        _hapticMed = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleMedium];
        [_hapticLight prepare];
        [_hapticMed prepare];
    }
    return self;
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat w = self.bounds.size.width;
    CGFloat h = self.bounds.size.height;
    CGFloat m = MIN(w, h);

    _gearCx = w * 0.50f;
    _gearCy = h * 0.12f;
    _smallBtnR = m * 0.048f;

    _dpadCx = w * 0.27f;
    _dpadCy = h * 0.43f;
    _dpadWellR = m * 0.23f;

    CGFloat abWellCx = w * 0.74f;
    CGFloat abWellCy = h * 0.41f;
    CGFloat sep = m * 0.105f;
    CGFloat ang = -24.0f * (CGFloat)M_PI / 180.0f;
    _bCx = abWellCx - cosf(ang) * sep;
    _bCy = abWellCy - sinf(ang) * sep;
    _aCx = abWellCx + cosf(ang) * sep;
    _aCy = abWellCy + sinf(ang) * sep;
    _abBtnR = m * 0.082f;

    _selectCx = w * 0.405f;
    _selectCy = h * 0.86f;
    _startCx = w * 0.595f;
    _startCy = h * 0.86f;
}

- (BOOL)isScanActive:(int)scan {
    for (UITouch *t in _actionTouches) {
        NSNumber *n = [_actionTouches objectForKey:t];
        if (n && n.intValue == scan) return YES;
    }
    return NO;
}

- (void)drawSmallRecessed:(CGContextRef)ctx cx:(CGFloat)cx cy:(CGFloat)cy r:(CGFloat)r label:(NSString *)lbl active:(BOOL)act {
    CGContextSetRGBFillColor(ctx, 0.067, 0.067, 0.082, 1.0);
    CGContextFillEllipseInRect(ctx, CGRectMake(cx - r*1.45, cy - r*1.45, r*2.9, r*2.9));

    if (act) CGContextSetRGBFillColor(ctx, 0.96, 0.62, 0.04, 1.0);
    else CGContextSetRGBFillColor(ctx, 0.28, 0.29, 0.31, 1.0);
    CGContextFillEllipseInRect(ctx, CGRectMake(cx - r, cy - r, r*2, r*2));

    CGContextSetRGBStrokeColor(ctx, 0.42, 0.44, 0.47, 1.0);
    CGContextSetLineWidth(ctx, 1.5);
    CGContextStrokeEllipseInRect(ctx, CGRectMake(cx - r, cy - r, r*2, r*2));

    if (lbl) {
        NSDictionary *attrs = @{
            NSFontAttributeName: [UIFont boldSystemFontOfSize:r * 1.1],
            NSForegroundColorAttributeName: [UIColor colorWithWhite:0.11 alpha:1.0]
        };
        CGSize sz = [lbl sizeWithAttributes:attrs];
        [lbl drawAtPoint:CGPointMake(cx - sz.width * 0.5, cy - sz.height * 0.5) withAttributes:attrs];
    }
}

- (void)drawAbBtn:(CGContextRef)ctx cx:(CGFloat)cx cy:(CGFloat)cy r:(CGFloat)r label:(NSString *)lbl active:(BOOL)act {
    if (act) CGContextSetRGBFillColor(ctx, 0.96, 0.62, 0.04, 1.0);
    else CGContextSetRGBFillColor(ctx, 0.29, 0.30, 0.34, 1.0);
    CGContextFillEllipseInRect(ctx, CGRectMake(cx - r, cy - r, r*2, r*2));

    CGContextSetRGBStrokeColor(ctx, act ? 1.0 : 0.46, act ? 1.0 : 0.47, act ? 1.0 : 0.51, 1.0);
    CGContextSetLineWidth(ctx, 1.6);
    CGContextStrokeEllipseInRect(ctx, CGRectMake(cx - r, cy - r, r*2, r*2));

    NSDictionary *attrs = @{
        NSFontAttributeName: [UIFont boldSystemFontOfSize:r * 0.95],
        NSForegroundColorAttributeName: act ? [UIColor blackColor] : [UIColor colorWithWhite:0.14 alpha:1.0]
    };
    CGSize sz = [lbl sizeWithAttributes:attrs];
    [lbl drawAtPoint:CGPointMake(cx - sz.width * 0.5, cy - sz.height * 0.5) withAttributes:attrs];
}

- (void)drawRect:(CGRect)rect {
    CGContextRef ctx = UIGraphicsGetCurrentContext();
    CGFloat w = self.bounds.size.width;
    CGFloat h = self.bounds.size.height;

    // 1. Lower Clamshell Matte Body
    UIBezierPath *bodyPath = [UIBezierPath bezierPathWithRoundedRect:CGRectInset(self.bounds, 1, 1)
                                                   byRoundingCorners:(UIRectCornerTopLeft|UIRectCornerTopRight|UIRectCornerBottomLeft|UIRectCornerBottomRight)
                                                         cornerRadii:CGSizeMake(28, 28)];
    [[UIColor colorWithRed:0.11 green:0.11 blue:0.125 alpha:1.0] setFill];
    [bodyPath fill];
    [[UIColor colorWithRed:0.17 green:0.17 blue:0.20 alpha:1.0] setStroke];
    bodyPath.lineWidth = 2.0;
    [bodyPath stroke];

    // 2. Right Edge Power LED
    [[UIColor colorWithRed:1.0 green:0.16 blue:0.16 alpha:1.0] setFill];
    [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(w - 10, h * 0.18, 9, 12) cornerRadius:2] fill];
    [[UIColor colorWithRed:0.06 green:0.06 blue:0.08 alpha:1.0] setFill];
    [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(w - 10, h * 0.24, 9, 11) cornerRadius:2] fill];

    // 3. Top-Center Gear / Settings Button
    [self drawSmallRecessed:ctx cx:_gearCx cy:_gearCy r:_smallBtnR label:@"*" active:NO];

    // 4. Left Circular Recessed Well + '+' Cross D-Pad
    CGContextSetRGBFillColor(ctx, 0.075, 0.075, 0.09, 1.0);
    CGContextFillEllipseInRect(ctx, CGRectMake(_dpadCx - _dpadWellR, _dpadCy - _dpadWellR, _dpadWellR*2, _dpadWellR*2));
    CGContextSetRGBStrokeColor(ctx, 0.15, 0.15, 0.18, 1.0);
    CGContextSetLineWidth(ctx, 1.5);
    CGContextStrokeEllipseInRect(ctx, CGRectMake(_dpadCx - _dpadWellR, _dpadCy - _dpadWellR, _dpadWellR*2, _dpadWellR*2));

    CGFloat armLen = _dpadWellR * 0.72f;
    CGFloat armHalfW = _dpadWellR * 0.25f;
    [[UIColor colorWithRed:0.267 green:0.275 blue:0.298 alpha:1.0] setFill];
    [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(_dpadCx - armLen, _dpadCy - armHalfW, armLen*2, armHalfW*2) cornerRadius:5] fill];
    [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(_dpadCx - armHalfW, _dpadCy - armLen, armHalfW*2, armLen*2) cornerRadius:5] fill];

    if (_activeDpadScan != 0) {
        [[UIColor colorWithRed:0.96 green:0.62 blue:0.04 alpha:0.48] setFill];
        if (_activeDpadScan == 16) {
            [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(_dpadCx - armHalfW, _dpadCy - armLen, armHalfW*2, armLen - armHalfW*0.5) cornerRadius:5] fill];
        } else if (_activeDpadScan == 17) {
            [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(_dpadCx - armHalfW, _dpadCy + armHalfW*0.5, armHalfW*2, armLen - armHalfW*0.5) cornerRadius:5] fill];
        } else if (_activeDpadScan == 14) {
            [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(_dpadCx - armLen, _dpadCy - armHalfW, armLen - armHalfW*0.5, armHalfW*2) cornerRadius:5] fill];
        } else if (_activeDpadScan == 15) {
            [[UIBezierPath bezierPathWithRoundedRect:CGRectMake(_dpadCx + armHalfW*0.5, _dpadCy - armHalfW, armLen - armHalfW*0.5, armHalfW*2) cornerRadius:5] fill];
        }
    }

    CGContextSetRGBFillColor(ctx, 0.22, 0.23, 0.25, 1.0);
    CGContextFillEllipseInRect(ctx, CGRectMake(_dpadCx - armHalfW*0.65, _dpadCy - armHalfW*0.65, armHalfW*1.3, armHalfW*1.3));

    // 5. Right Angled Pill Well + B & A Circular Buttons
    CGContextSaveGState(ctx);
    CGFloat abMidX = (_bCx + _aCx) * 0.5f;
    CGFloat abMidY = (_bCy + _aCy) * 0.5f;
    CGContextTranslateCTM(ctx, abMidX, abMidY);
    CGContextRotateCTM(ctx, -24.0f * (CGFloat)M_PI / 180.0f);
    CGFloat pillW = hypotf(_aCx - _bCx, _aCy - _bCy) * 0.5f + _abBtnR * 1.38f;
    CGFloat pillH = _abBtnR * 1.35f;
    UIBezierPath *pill = [UIBezierPath bezierPathWithRoundedRect:CGRectMake(-pillW, -pillH, pillW*2, pillH*2) cornerRadius:pillH];
    [[UIColor colorWithRed:0.075 green:0.075 blue:0.09 alpha:1.0] setFill];
    [pill fill];
    [[UIColor colorWithRed:0.15 green:0.15 blue:0.18 alpha:1.0] setStroke];
    pill.lineWidth = 1.5;
    [pill stroke];
    CGContextRestoreGState(ctx);

    [self drawAbBtn:ctx cx:_bCx cy:_bCy r:_abBtnR label:@"B" active:[self isScanActive:200]];
    [self drawAbBtn:ctx cx:_aCx cy:_aCy r:_abBtnR label:@"A" active:[self isScanActive:201]];

    // 6. Center 4x4 Speaker Grille Dots
    CGFloat gx0 = w * 0.50f - 21.0f;
    CGFloat gy0 = h * 0.63f;
    CGContextSetRGBFillColor(ctx, 0.03, 0.03, 0.04, 1.0);
    for (int r = 0; r < 4; r++) {
        for (int c = 0; c < 4; c++) {
            CGContextFillEllipseInRect(ctx, CGRectMake(gx0 + c*14.0f - 3.0f, gy0 + r*12.0f - 3.0f, 6.0f, 6.0f));
        }
    }

    // 7. Bottom-Center SELECT (164) & START (165) Buttons
    [self drawSmallRecessed:ctx cx:_selectCx cy:_selectCy r:_smallBtnR label:nil active:[self isScanActive:164]];
    [self drawSmallRecessed:ctx cx:_startCx cy:_startCy r:_smallBtnR label:nil active:[self isScanActive:165]];

    NSDictionary *lblAttr = @{
        NSFontAttributeName: [UIFont boldSystemFontOfSize:9.5],
        NSForegroundColorAttributeName: [UIColor colorWithWhite:0.42 alpha:1.0]
    };
    CGSize selSz = [@"SELECT" sizeWithAttributes:lblAttr];
    [@"SELECT" drawAtPoint:CGPointMake(_selectCx - selSz.width*0.5, _selectCy + _smallBtnR*1.65) withAttributes:lblAttr];
    CGSize staSz = [@"START" sizeWithAttributes:lblAttr];
    [@"START" drawAtPoint:CGPointMake(_startCx - staSz.width*0.5, _startCy + _smallBtnR*1.65) withAttributes:lblAttr];
}

- (int)hitTestActionScanAt:(CGPoint)pt {
    if (hypotf(pt.x - _bCx, pt.y - _bCy) <= _abBtnR * 1.38f) return 200; // B
    if (hypotf(pt.x - _aCx, pt.y - _aCy) <= _abBtnR * 1.38f) return 201; // A
    if (hypotf(pt.x - _selectCx, pt.y - _selectCy) <= _smallBtnR * 1.95f) return 164; // SELECT (Soft L)
    if (hypotf(pt.x - _startCx, pt.y - _startCy) <= _smallBtnR * 1.95f) return 165; // START (Soft R)
    return 0;
}

- (void)updateDpadAt:(CGPoint)pt {
    CGFloat dx = pt.x - _dpadCx;
    CGFloat dy = pt.y - _dpadCy;
    CGFloat dist = hypotf(dx, dy);
    if (dist < _dpadWellR * 0.16f) {
        if (_activeDpadScan != 0) {
            send_vm_key(_activeDpadScan, 0);
            _activeDpadScan = 0;
            [self setNeedsDisplay];
        }
        return;
    }
    int next = (fabsf(dx) > fabsf(dy)) ? (dx > 0 ? 15 : 14) : (dy > 0 ? 17 : 16);
    if (next != _activeDpadScan) {
        if (_activeDpadScan != 0) {
            pthread_mutex_lock(&g_vm_mutex);
            g_pending_keyup[_activeDpadScan] = 0;
            g_key_is_down[_activeDpadScan] = 0;
            vm_key_event((uint32_t)_activeDpadScan, 0);
            pthread_mutex_unlock(&g_vm_mutex);
        }
        _activeDpadScan = next;
        send_vm_key(_activeDpadScan, 1);
        [_hapticLight impactOccurred];
        [self setNeedsDisplay];
    }
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    for (UITouch *t in touches) {
        CGPoint pt = [t locationInView:self];
        if (hypotf(pt.x - _gearCx, pt.y - _gearCy) <= _smallBtnR * 2.1f) {
            [_hapticMed impactOccurred];
            [self.ownerVc showSettingsSheet];
            continue;
        }
        if (!_dpadTouch && hypotf(pt.x - _dpadCx, pt.y - _dpadCy) <= _dpadWellR * 1.25f) {
            _dpadTouch = t;
            [self updateDpadAt:pt];
            continue;
        }
        int scan = [self hitTestActionScanAt:pt];
        if (scan != 0) {
            [_actionTouches setObject:@(scan) forKey:t];
            [_hapticMed impactOccurred];
            send_vm_key(scan, 1);
            [self setNeedsDisplay];
        }
    }
}

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    for (UITouch *t in touches) {
        CGPoint pt = [t locationInView:self];
        if (t == _dpadTouch) {
            [self updateDpadAt:pt];
        } else {
            NSNumber *prevNum = [_actionTouches objectForKey:t];
            int prev = prevNum ? prevNum.intValue : 0;
            int next = [self hitTestActionScanAt:pt];
            if (prev != next) {
                if (prev != 0) send_vm_key(prev, 0);
                if (next != 0) {
                    [_hapticLight impactOccurred];
                    send_vm_key(next, 1);
                    [_actionTouches setObject:@(next) forKey:t];
                } else {
                    [_actionTouches removeObjectForKey:t];
                }
                [self setNeedsDisplay];
            }
        }
    }
}

- (void)endTouches:(NSSet<UITouch *> *)touches {
    for (UITouch *t in touches) {
        if (t == _dpadTouch) {
            _dpadTouch = nil;
            if (_activeDpadScan != 0) {
                send_vm_key(_activeDpadScan, 0);
                _activeDpadScan = 0;
                [self setNeedsDisplay];
            }
        }
        NSNumber *prevNum = [_actionTouches objectForKey:t];
        if (prevNum) {
            send_vm_key(prevNum.intValue, 0);
            [_actionTouches removeObjectForKey:t];
            [self setNeedsDisplay];
        }
    }
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self endTouches:touches];
}

- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self endTouches:touches];
}
@end

@implementation SpMainViewController {
    UIView *_screenView;
    UILabel *_lblLeft;
    UILabel *_lblRight;
    GbaSpControllerView *_deckView;
    CADisplayLink *_displayLink;
    CFTimeInterval _lastStepTime;
    CFTimeInterval _fpsTimer;
    int _renderFrames;
    int _simTicks;
    CGColorSpaceRef _colorSpace;
}

- (BOOL)prefersStatusBarHidden {
    return YES;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor colorWithRed:0.047 green:0.047 blue:0.055 alpha:1.0];
    _colorSpace = CGColorSpaceCreateDeviceRGB();

    g_local_uid = (arc4random() & 0x7ffffffeu) + 1u;
    udp_init_socket();

    NSString *sisPath = [[NSBundle mainBundle] pathForResource:@"game" ofType:@"sis"];
    if (sisPath) {
        NSData *sisData = [NSData dataWithContentsOfFile:sisPath];
        if (sisData) boot_from_sis_data((const uint8_t *)sisData.bytes, sisData.length);
    }

    start_ios_audio();

    _displayLink = [CADisplayLink displayLinkWithTarget:self selector:@selector(onFrame:)];
    if (@available(iOS 15.0, *)) {
        _displayLink.preferredFrameRateRange = CAFrameRateRangeMake(60, 120, 120);
    }
    [_displayLink addToRunLoop:[NSRunLoop mainRunLoop] forMode:NSRunLoopCommonModes];
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    if (_deckView) return;

    UIEdgeInsets safe = self.view.safeAreaInsets;
    CGRect b = UIEdgeInsetsInsetRect(self.view.bounds, UIEdgeInsetsMake(MAX(safe.top, 8), 8, MAX(safe.bottom, 8), 8));

    CGFloat hingeH = 26.0f;
    CGFloat upperH = (b.size.height - hingeH) * 0.53f;
    CGFloat lowerH = b.size.height - hingeH - upperH;

    // 1. Upper Clamshell Lid
    UIView *upperLid = [[UIView alloc] initWithFrame:CGRectMake(b.origin.x, b.origin.y, b.size.width, upperH)];
    upperLid.backgroundColor = [UIColor colorWithRed:0.094 green:0.094 blue:0.11 alpha:1.0];
    upperLid.layer.cornerRadius = 26.0f;
    upperLid.layer.borderWidth = 2.0f;
    upperLid.layer.borderColor = [UIColor colorWithRed:0.16 green:0.16 blue:0.19 alpha:1.0].CGColor;
    [self.view addSubview:upperLid];

    UIView *bezel = [[UIView alloc] initWithFrame:CGRectInset(upperLid.bounds, 12, 10)];
    bezel.backgroundColor = [UIColor blackColor];
    bezel.layer.cornerRadius = 18.0f;
    [upperLid addSubview:bezel];

    _lblLeft = [[UILabel alloc] initWithFrame:CGRectMake(12, 6, bezel.bounds.size.width * 0.5 - 12, 16)];
    _lblLeft.text = @"POWER ON";
    _lblLeft.font = [UIFont boldSystemFontOfSize:10.0];
    _lblLeft.textColor = [UIColor colorWithRed:0.42 green:0.44 blue:0.47 alpha:1.0];
    [bezel addSubview:_lblLeft];

    _lblRight = [[UILabel alloc] initWithFrame:CGRectMake(bezel.bounds.size.width * 0.5, 6, bezel.bounds.size.width * 0.5 - 12, 16)];
    _lblRight.text = @"BATTERY FULL";
    _lblRight.font = [UIFont boldSystemFontOfSize:10.0];
    _lblRight.textColor = [UIColor colorWithRed:0.42 green:0.44 blue:0.47 alpha:1.0];
    _lblRight.textAlignment = NSTextAlignmentRight;
    [bezel addSubview:_lblRight];

    CGFloat availW = bezel.bounds.size.width - 20.0f;
    CGFloat availH = bezel.bounds.size.height - 48.0f;
    CGFloat scrW = availH * (176.0f / 208.0f);
    CGFloat scrH = availH;
    if (scrW > availW) {
        scrW = availW;
        scrH = availW * (208.0f / 176.0f);
    }
    _screenView = [[UIView alloc] initWithFrame:CGRectMake((bezel.bounds.size.width - scrW) * 0.5f, 24.0f + (availH - scrH) * 0.5f, scrW, scrH)];
    _screenView.backgroundColor = [UIColor blackColor];
    _screenView.layer.cornerRadius = 6.0f;
    _screenView.layer.masksToBounds = YES;
    [bezel addSubview:_screenView];

    UILabel *logo = [[UILabel alloc] initWithFrame:CGRectMake(0, bezel.bounds.size.height - 22.0f, bezel.bounds.size.width, 18.0f)];
    logo.text = @"GAME BOY ADVANCE SP";
    logo.font = [UIFont fontWithDescriptor:[[UIFont boldSystemFontOfSize:13.0].fontDescriptor fontDescriptorWithSymbolicTraits:(UIFontDescriptorTraitBold | UIFontDescriptorTraitItalic)] size:13.0];
    logo.textColor = [UIColor colorWithRed:0.88 green:0.91 blue:0.94 alpha:1.0];
    logo.textAlignment = NSTextAlignmentCenter;
    [bezel addSubview:logo];

    // 2. Middle 3D Cylindrical Hinge
    UIView *hinge = [[UIView alloc] initWithFrame:CGRectMake(b.origin.x + 4, b.origin.y + upperH, b.size.width - 8, hingeH)];
    CAGradientLayer *grad = [CAGradientLayer layer];
    grad.frame = hinge.bounds;
    grad.colors = @[
        (id)[UIColor colorWithRed:0.03 green:0.03 blue:0.04 alpha:1.0].CGColor,
        (id)[UIColor colorWithRed:0.18 green:0.18 blue:0.20 alpha:1.0].CGColor,
        (id)[UIColor colorWithRed:0.12 green:0.12 blue:0.14 alpha:1.0].CGColor,
        (id)[UIColor colorWithRed:0.03 green:0.03 blue:0.04 alpha:1.0].CGColor
    ];
    [hinge.layer addSublayer:grad];
    [self.view addSubview:hinge];

    // 3. Lower Controller Deck
    _deckView = [[GbaSpControllerView alloc] initWithFrame:CGRectMake(b.origin.x, b.origin.y + upperH + hingeH, b.size.width, lowerH)];
    _deckView.ownerVc = self;
    [self.view addSubview:_deckView];
}

- (void)renderVmScreen {
    if (!g_vm_ready || !_screenView) return;
    int w, h;
    const uint32_t *px;
    pthread_mutex_lock(&g_vm_mutex);
    if (g_upscale_mode == 0) {
        w = 176; h = 208;
        px = vm_get_rgba_ptr();
        _screenView.layer.magnificationFilter = kCAFilterNearest;
    } else {
        w = 704; h = 832;
        vm_set_upscale_mode((uint32_t)g_upscale_mode);
        px = vm_get_upscaled_rgba_ptr();
        _screenView.layer.magnificationFilter = kCAFilterLinear;
    }
    CGDataProviderRef prov = CGDataProviderCreateWithData(NULL, px, w * h * 4, NULL);
    CGImageRef img = CGImageCreate(
        w, h, 8, 32, w * 4, _colorSpace,
        kCGBitmapByteOrder32Big | kCGImageAlphaNoneSkipLast,
        prov, NULL, false, kCGRenderingIntentDefault
    );
    CGDataProviderRelease(prov);
    pthread_mutex_unlock(&g_vm_mutex);

    if (img) {
        _screenView.layer.contents = (__bridge id)img;
        CGImageRelease(img);
    }
}

- (void)onFrame:(CADisplayLink *)link {
    udp_poll_rx();
    CFTimeInterval now = link.timestamp;
    if (_lastStepTime == 0) {
        _lastStepTime = now;
        _fpsTimer = now;
    }
    _renderFrames++;
    double stepSec = 1.0 / (double)MAX(20, g_target_fps);
    if (now - _lastStepTime >= stepSec) {
        _lastStepTime = now;
        if (g_vm_ready && !g_paused) {
            pthread_mutex_lock(&g_vm_mutex);
            vm_tick(33);
            g_tick_counter++;
            flush_pending_keyups_locked();
            udp_pump_tx_locked();
            if (vm_consume_cfg_dirty()) {
                NSData *cfg = [NSData dataWithBytes:vm_get_cfg_buf() length:0x68];
                [[NSUserDefaults standardUserDefaults] setObject:cfg forKey:@"game_cfg_104"];
            }
            pthread_mutex_unlock(&g_vm_mutex);
            _simTicks++;
            if ((_simTicks & 15) == 0) udp_send_heartbeat();
            [self renderVmScreen];
        }
    }
    if (now - _fpsTimer >= 1.0) {
        int rFps = (int)round(_renderFrames / (now - _fpsTimer));
        int tps = (int)round(_simTicks / (now - _fpsTimer));
        _renderFrames = 0;
        _simTicks = 0;
        _fpsTimer = now;
        udp_send_heartbeat();

        int activePeers = 0;
        double curT = CFAbsoluteTimeGetCurrent();
        for (int i = 0; i < g_peer_count; i++) {
            if (curT - g_peer_last_seen[i] <= 15.0) activePeers++;
        }
        if (activePeers > 0) {
            _lblLeft.text = [NSString stringWithFormat:@"LAN READY (%d PEER)", activePeers];
            _lblLeft.textColor = [UIColor colorWithRed:0.06 green:0.73 blue:0.51 alpha:1.0];
        } else {
            _lblLeft.text = @"POWER ON";
            _lblLeft.textColor = [UIColor colorWithRed:0.42 green:0.44 blue:0.47 alpha:1.0];
        }
        _lblRight.text = [NSString stringWithFormat:@"%d FPS (%d TPS)", rFps, tps];
    }
}

- (void)showSettingsSheet {
    NSArray *modes = @[@"Retro Pixel 1x (Fastest)", @"xBR Crisp 4x", @"xBR+Anime4K 4x"];
    UIAlertController *ac = [UIAlertController alertControllerWithTitle:@"EXPLODE ARENA SP — NATIVE iOS"
                                                                message:@"Zero-Config Wi-Fi/Hotspot UDP Multiplayer Active"
                                                         preferredStyle:UIAlertControllerStyleActionSheet];
    [ac addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Upscaler: %@", modes[g_upscale_mode]]
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        g_upscale_mode = (g_upscale_mode + 1) % 3;
        [self renderVmScreen];
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Target Speed: %d FPS", g_target_fps]
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        g_target_fps = (g_target_fps == 30) ? 45 : (g_target_fps == 45 ? 60 : (g_target_fps == 60 ? 20 : 30));
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Audio: %@", g_audio_muted ? @"MUTE" : @"ON"]
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        g_audio_muted = !g_audio_muted;
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:@"[Cheat] MAX POWERUPS (In-Game)"
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        pthread_mutex_lock(&g_vm_mutex); vm_apply_cheat(20); pthread_mutex_unlock(&g_vm_mutex);
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"[Cheat] GOD MODE (%@)", g_god_mode ? @"ON" : @"OFF"]
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        g_god_mode = !g_god_mode;
        pthread_mutex_lock(&g_vm_mutex); vm_apply_cheat(21); pthread_mutex_unlock(&g_vm_mutex);
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:@"[Cheat] IDRULEZ (Unlock All Stages)"
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        pthread_mutex_lock(&g_vm_mutex); vm_apply_cheat(1); pthread_mutex_unlock(&g_vm_mutex);
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:@"[Cheat] Cycle Secret Alien (ALIEN1..7)"
                                           style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *a) {
        int c = g_alien_cycle;
        g_alien_cycle = (g_alien_cycle >= 10) ? 4 : (g_alien_cycle + 1);
        pthread_mutex_lock(&g_vm_mutex); vm_apply_cheat((uint32_t)c); pthread_mutex_unlock(&g_vm_mutex);
    }]];
    [ac addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    if (ac.popoverPresentationController) {
        ac.popoverPresentationController.sourceView = self.view;
        ac.popoverPresentationController.sourceRect = CGRectMake(self.view.bounds.size.width * 0.5, self.view.bounds.size.height * 0.5, 1, 1);
    }
    [self presentViewController:ac animated:YES completion:nil];
}
@end

@interface AppDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
@end

@implementation AppDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = [[SpMainViewController alloc] init];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char * argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([AppDelegate class]));
    }
}
"""
    objc_file = os.path.join(work, "main.m")
    with open(objc_file, "w") as f:
        f.write(objc_src)

    vm_c = os.path.join(REPO_DIR, "src", "vm.c")
    bin_out = os.path.join(app_dir, "ExplodeArenaSP")

    subprocess.run([
        CLANG, "-arch", "arm64",
        "-isysroot", SDK_PATH,
        "-miphoneos-version-min=14.0",
        "-O3", "-fobjc-arc",
        "-Wno-deprecated-declarations",
        vm_c, objc_file,
        "-framework", "UIKit",
        "-framework", "Foundation",
        "-framework", "CoreGraphics",
        "-framework", "QuartzCore",
        "-framework", "AudioToolbox",
        "-framework", "AVFoundation",
        "-lz",
        "-o", bin_out
    ], check=True)

    subprocess.run(["ldid", "-S", bin_out], check=True)

    out_ipa = os.path.join(OUT_DIR, "ExplodeArena-S60-Native-iOS.ipa")
    if os.path.exists(out_ipa):
        os.remove(out_ipa)
    subprocess.run(["zip", "-qry", out_ipa, "Payload"], cwd=work, check=True)
    print(f"SUCCESS: Built Native iOS IPA -> {out_ipa} ({os.path.getsize(out_ipa):,} bytes)")

def build_webview_ios_ipa():
    work = "/tmp/explode_ios_webview_build"
    if os.path.exists(work):
        shutil.rmtree(work)
    app_dir = os.path.join(work, "Payload", "ExplodeArenaWebSP.app")
    os.makedirs(os.path.join(app_dir, "www", "js"), exist_ok=True)

    make_icon_png(os.path.join(app_dir, "AppIcon60x60@2x.png"), 120, 120)
    make_icon_png(os.path.join(app_dir, "AppIcon60x60@3x.png"), 180, 180)
    make_icon_png(os.path.join(app_dir, "Icon.png"), 180, 180)

    shutil.copy(os.path.join(REPO_DIR, "js", "vm_wasm.js"), os.path.join(app_dir, "www", "js", "vm_wasm.js"))
    shutil.copy(os.path.join(REPO_DIR, "js", "sis_parser.js"), os.path.join(app_dir, "www", "js", "sis_parser.js"))

    if sis_input and os.path.isfile(sis_input):
        with open(sis_input, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        with open(os.path.join(app_dir, "www", "js", "builtin_sis.js"), "w") as f:
            f.write(f'window.BUILTIN_SIS_BASE64 = "{b64}";\n')
    else:
        with open(os.path.join(app_dir, "www", "js", "builtin_sis.js"), "w") as f:
            f.write("// BYO-SIS mode\n")

    with open(os.path.join(REPO_DIR, "index.html"), "r") as f:
        html = f.read()

    ios_css_extra = """
    body.ios-apk .topbar { display: none; }
    body.ios-apk .workspace { padding: 4px 6px 8px; gap: 8px; display: flex; flex-direction: column; align-items: center; }
    body.ios-apk .handheld-column { width: 100%; }
    body.ios-apk .nokia-chassis { max-width: 440px; width: 100%; }
    body.ios-apk .sp-upper-lid { padding: 10px 12px 10px; }
    body.ios-apk .screen-bezel { padding: 8px 10px 10px; }
    body.ios-apk .canvas-wrap { width: 100%; max-width: 330px; height: auto; max-height: 45dvh; }
    body.ios-apk .sp-hinge { height: 28px; }
    body.ios-apk .sp-lower-deck { padding: 12px 16px 18px; }
    body.ios-apk .studio-deck { display: none; width: 100%; max-width: 440px; }
    body.ios-apk.drawer-open .studio-deck { display: flex; }
"""
    html = html.replace("</style>", ios_css_extra + "\n  </style>")
    html = html.replace("<body>", '<body class="ios-apk">')
    html = html.replace('<script src="js/vm_wasm.js"></script>', '<script src="js/builtin_sis.js"></script>\n  <script src="js/vm_wasm.js"></script>')
    html = html.replace(
        'document.getElementById("btn-toggle-numpad").addEventListener("click", (e) => {',
        '''document.getElementById("btn-toggle-numpad").addEventListener("click", (e) => {
        document.body.classList.toggle("drawer-open");'''
    )
    with open(os.path.join(app_dir, "www", "index.html"), "w") as f:
        f.write(html)

    info_plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>Explode Arena Web</string>
    <key>CFBundleExecutable</key>
    <string>ExplodeArenaWebSP</string>
    <key>CFBundleIdentifier</key>
    <string>im.agusibrah.explodearena.ios.web</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ExplodeArenaWebSP</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleVersion</key>
    <string>2</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>MinimumOSVersion</key>
    <string>14.0</string>
    <key>UIDeviceFamily</key>
    <array>
        <integer>1</integer>
        <integer>2</integer>
    </array>
    <key>UILaunchScreen</key>
    <dict/>
    <key>UIRequiredDeviceCapabilities</key>
    <array>
        <string>arm64</string>
    </array>
    <key>UIStatusBarHidden</key>
    <true/>
    <key>UIViewControllerBasedStatusBarAppearance</key>
    <false/>
    <key>UISupportedInterfaceOrientations</key>
    <array>
        <string>UIInterfaceOrientationPortrait</string>
    </array>
    <key>CFBundleIcons</key>
    <dict>
        <key>CFBundlePrimaryIcon</key>
        <dict>
            <key>CFBundleIconFiles</key>
            <array>
                <string>AppIcon60x60</string>
                <string>Icon.png</string>
            </array>
        </dict>
    </dict>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
    <key>NSLocalNetworkUsageDescription</key>
    <string>Explode Arena SP uses the local Wi-Fi or Hotspot network to automatically discover nearby Android and iOS players for multiplayer matches.</string>
</dict>
</plist>
"""
    with open(os.path.join(app_dir, "Info.plist"), "w") as f:
        f.write(info_plist)

    wk_objc = r"""
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <fcntl.h>
#include <unistd.h>

#define UDP_PORT 18765
#define MAX_PEERS 8

@interface WkViewController : UIViewController <WKScriptMessageHandler>
@property (strong, nonatomic) WKWebView *webView;
@property (strong, nonatomic) UIImpactFeedbackGenerator *haptic;
@property (strong, nonatomic) NSTimer *udpTimer;
@end

@implementation WkViewController {
    int _udpSock;
    uint32_t _localUid;
    struct in_addr _peerAddrs[MAX_PEERS];
    double _peerLastSeen[MAX_PEERS];
    int _peerCount;
    int _tickCount;
}

- (BOOL)prefersStatusBarHidden { return YES; }

- (void)initUdpSocket {
    _localUid = (arc4random() & 0x7ffffffeu) + 1u;
    _udpSock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (_udpSock < 0) return;
    int yes = 1;
    setsockopt(_udpSock, SOL_SOCKET, SO_BROADCAST, &yes, sizeof(yes));
    setsockopt(_udpSock, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    setsockopt(_udpSock, SOL_SOCKET, SO_REUSEPORT, &yes, sizeof(yes));
    int flags = fcntl(_udpSock, F_GETFL, 0);
    fcntl(_udpSock, F_SETFL, flags | O_NONBLOCK);

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(UDP_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    bind(_udpSock, (struct sockaddr *)&addr, sizeof(addr));
}

- (void)sendUdpToAddr:(struct in_addr)dst data:(const uint8_t *)buf len:(size_t)len {
    if (_udpSock < 0) return;
    struct sockaddr_in sa;
    memset(&sa, 0, sizeof(sa));
    sa.sin_family = AF_INET;
    sa.sin_port = htons(UDP_PORT);
    sa.sin_addr = dst;
    sendto(_udpSock, buf, len, 0, (struct sockaddr *)&sa, sizeof(sa));
}

- (void)broadcastUdpPacket:(NSData *)pktData alsoSweep:(BOOL)sweep {
    if (_udpSock < 0 || !pktData) return;
    const uint8_t *pkt = (const uint8_t *)pktData.bytes;
    size_t len = pktData.length;
    double now = CFAbsoluteTimeGetCurrent();
    int sentUnicast = 0;
    for (int i = 0; i < _peerCount; i++) {
        if (now - _peerLastSeen[i] <= 15.0) {
            [self sendUdpToAddr:_peerAddrs[i] data:pkt len:len];
            sentUnicast++;
        }
    }
    if (!sweep && sentUnicast > 0) return;

    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        const uint8_t *b = (const uint8_t *)pktData.bytes;
        size_t l = pktData.length;
        struct ifaddrs *ifap = NULL;
        if (getifaddrs(&ifap) == 0) {
            for (struct ifaddrs *ifa = ifap; ifa != NULL; ifa = ifa->ifa_next) {
                if (!ifa->ifa_addr || ifa->ifa_addr->sa_family != AF_INET) continue;
                if (!(ifa->ifa_flags & IFF_UP) || (ifa->ifa_flags & IFF_LOOPBACK)) continue;
                struct sockaddr_in *sin = (struct sockaddr_in *)ifa->ifa_addr;
                uint32_t ip_h = ntohl(sin->sin_addr.s_addr);
                if ((ip_h >> 24) == 127 || (ip_h >> 24) == 169) continue;

                if ((ifa->ifa_flags & IFF_BROADCAST) && ifa->ifa_dstaddr) {
                    struct sockaddr_in *bcast = (struct sockaddr_in *)ifa->ifa_dstaddr;
                    [self sendUdpToAddr:bcast->sin_addr data:b len:l];
                }
                uint32_t net_prefix = ip_h & 0xffffff00u;
                uint32_t my_last = ip_h & 0xffu;
                for (uint32_t host = 1; host <= 254; host++) {
                    if (host == my_last) continue;
                    struct in_addr target;
                    target.s_addr = htonl(net_prefix | host);
                    [self sendUdpToAddr:target data:b len:l];
                }
            }
            freeifaddrs(ifap);
        }
    });
}

- (void)pollUdpSocket {
    if (_udpSock < 0) return;
    _tickCount++;
    if ((_tickCount % 30) == 1) {
        uint8_t ping[6] = {
            (uint8_t)(_localUid & 0xff),
            (uint8_t)((_localUid >> 8) & 0xff),
            (uint8_t)((_localUid >> 16) & 0xff),
            (uint8_t)((_localUid >> 24) & 0xff),
            0xfd, 0x01
        };
        [self broadcastUdpPacket:[NSData dataWithBytes:ping length:6] alsoSweep:(_peerCount == 0)];
    }

    uint8_t rx[256];
    struct sockaddr_in src_sa;
    socklen_t slen = sizeof(src_sa);
    while (1) {
        ssize_t n = recvfrom(_udpSock, rx, sizeof(rx), 0, (struct sockaddr *)&src_sa, &slen);
        if (n <= 4) break;
        uint32_t senderUid = (uint32_t)rx[0] | ((uint32_t)rx[1] << 8) | ((uint32_t)rx[2] << 16) | ((uint32_t)rx[3] << 24);
        if (senderUid == _localUid || senderUid == 0) continue;

        double now = CFAbsoluteTimeGetCurrent();
        int found = -1;
        for (int i = 0; i < _peerCount; i++) {
            if (_peerAddrs[i].s_addr == src_sa.sin_addr.s_addr) { found = i; break; }
        }
        if (found < 0 && _peerCount < MAX_PEERS) {
            found = _peerCount++;
            _peerAddrs[found] = src_sa.sin_addr;
        }
        if (found >= 0) _peerLastSeen[found] = now;

        if (rx[4] == 0xfd) {
            if (n > 5 && rx[5] == 0x01) {
                uint8_t pong[6] = {
                    (uint8_t)(_localUid & 0xff),
                    (uint8_t)((_localUid >> 8) & 0xff),
                    (uint8_t)((_localUid >> 16) & 0xff),
                    (uint8_t)((_localUid >> 24) & 0xff),
                    0xfd, 0x02
                };
                [self sendUdpToAddr:src_sa.sin_addr data:pong len:6];
            }
            [self.webView evaluateJavaScript:[NSString stringWithFormat:@"if(window.__onNativeUdpRx)window.__onNativeUdpRx('',%d);", _peerCount] completionHandler:nil];
            continue;
        }

        NSData *pay = [NSData dataWithBytes:(rx + 4) length:(n - 4)];
        NSString *b64 = [pay base64EncodedStringWithOptions:0];
        NSString *js = [NSString stringWithFormat:@"if(window.__onNativeUdpRx)window.__onNativeUdpRx('%@',%d);", b64, _peerCount];
        [self.webView evaluateJavaScript:js completionHandler:nil];
    }
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor colorWithRed:0.047 green:0.047 blue:0.055 alpha:1.0];
    self.haptic = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
    [self.haptic prepare];
    [self initUdpSocket];

    WKWebViewConfiguration *cfg = [[WKWebViewConfiguration alloc] init];
    cfg.allowsInlineMediaPlayback = YES;
    cfg.mediaTypesRequiringUserActionForPlayback = WKAudiovisualMediaTypeNone;
    [cfg.userContentController addScriptMessageHandler:self name:@"haptic"];
    [cfg.userContentController addScriptMessageHandler:self name:@"udpTx"];

    WKUserScript *bridgeScript = [[WKUserScript alloc] initWithSource:
        @"window.AndroidBridge = {"
        @"  vibrate: function(ms) { try { window.webkit.messageHandlers.haptic.postMessage(ms); } catch(e){} },"
        @"  sendUdp: function(b64) { try { window.webkit.messageHandlers.udpTx.postMessage(b64); } catch(e){} }"
        @"};"
        injectionTime:WKUserScriptInjectionTimeAtDocumentStart
        forMainFrameOnly:YES];
    [cfg.userContentController addUserScript:bridgeScript];

    self.webView = [[WKWebView alloc] initWithFrame:self.view.bounds configuration:cfg];
    self.webView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.webView.opaque = NO;
    self.webView.backgroundColor = self.view.backgroundColor;
    self.webView.scrollView.bounces = NO;
    [self.view addSubview:self.webView];

    NSString *htmlPath = [[NSBundle mainBundle] pathForResource:@"index" ofType:@"html" inDirectory:@"www"];
    if (htmlPath) {
        NSURL *htmlUrl = [NSURL fileURLWithPath:htmlPath];
        NSURL *wwwDir = [htmlUrl URLByDeletingLastPathComponent];
        [self.webView loadFileURL:htmlUrl allowingReadAccessToURL:wwwDir];
    }

    self.udpTimer = [NSTimer scheduledTimerWithTimeInterval:0.020 target:self selector:@selector(pollUdpSocket) userInfo:nil repeats:YES];
}

- (void)userContentController:(WKUserContentController *)userContentController didReceiveScriptMessage:(WKScriptMessage *)message {
    if ([message.name isEqualToString:@"haptic"]) {
        [self.haptic impactOccurred];
    } else if ([message.name isEqualToString:@"udpTx"] && [message.body isKindOfClass:[NSString class]]) {
        NSData *pay = [[NSData alloc] initWithBase64EncodedString:(NSString *)message.body options:0];
        if (pay && pay.length > 0) {
            NSMutableData *pkt = [NSMutableData dataWithCapacity:pay.length + 4];
            uint8_t hdr[4] = {
                (uint8_t)(_localUid & 0xff),
                (uint8_t)((_localUid >> 8) & 0xff),
                (uint8_t)((_localUid >> 16) & 0xff),
                (uint8_t)((_localUid >> 24) & 0xff)
            };
            [pkt appendBytes:hdr length:4];
            [pkt appendData:pay];
            const uint8_t *pb = (const uint8_t *)pay.bytes;
            BOOL isDisc = (pb[0] == 0xfe || pb[0] == 0xff);
            [self broadcastUdpPacket:pkt alsoSweep:isDisc];
        }
    }
}
@end

@interface WkAppDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
@end

@implementation WkAppDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    [UIApplication sharedApplication].idleTimerDisabled = YES;
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = [[WkViewController alloc] init];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char * argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass([WkAppDelegate class]));
    }
}
"""
    wk_file = os.path.join(work, "wk_main.m")
    with open(wk_file, "w") as f:
        f.write(wk_objc)

    bin_out = os.path.join(app_dir, "ExplodeArenaWebSP")
    subprocess.run([
        CLANG, "-arch", "arm64",
        "-isysroot", SDK_PATH,
        "-miphoneos-version-min=14.0",
        "-O3", "-fobjc-arc",
        wk_file,
        "-framework", "UIKit",
        "-framework", "Foundation",
        "-framework", "WebKit",
        "-o", bin_out
    ], check=True)

    subprocess.run(["ldid", "-S", bin_out], check=True)

    out_ipa = os.path.join(OUT_DIR, "ExplodeArena-S60-WebView-iOS.ipa")
    if os.path.exists(out_ipa):
        os.remove(out_ipa)
    subprocess.run(["zip", "-qry", out_ipa, "Payload"], cwd=work, check=True)
    print(f"SUCCESS: Built WebView iOS IPA -> {out_ipa} ({os.path.getsize(out_ipa):,} bytes)")

if __name__ == "__main__":
    build_native_ios_ipa()
    build_webview_ios_ipa()
