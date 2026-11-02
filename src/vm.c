#include <stdint.h>
#include <stddef.h>

#define WASM_EXPORT(name) __attribute__((visibility("default"), export_name(name)))

#define MEM_SIZE (16 * 1024 * 1024)
#define ADDR_MASK (MEM_SIZE - 1)

#define PAK_MAX_SIZE 420000
#define CFG_MAX_SIZE 256

#define FB_GUEST_ADDR 0x10200000u
#define HEAP_START_ADDR 0x10300000u
#define HEAP_END_ADDR   0x10e00000u
#define STACK_TOP_ADDR  0x10f00000u

static uint8_t mem[MEM_SIZE];
static uint8_t pak_data[PAK_MAX_SIZE];
static uint32_t pak_size = 0;

static uint8_t game_cfg[CFG_MAX_SIZE];
static uint8_t last_cgame_cfg[0x68];
static uint32_t game_cfg_size = 36;
static uint32_t game_cfg_dirty = 0;

static uint32_t rgba_fb[176 * 208];
static uint32_t dedith_1x[176 * 208];
static uint32_t upscaled_2x[352 * 416];
static uint32_t refine_2x[352 * 416];
static uint32_t xbr_4x[704 * 832];
static uint32_t upscaled_4x[704 * 832];
static uint16_t luma_buf[704 * 832];
static uint32_t upscale_mode = 2; // 0 = Pixelated, 1 = EPX/Scale4x Crisp, 2 = xBR + Anime4K + De-Dither 4x Ultra Smooth
static int16_t pcm_out[768];

static uint32_t reg[16];
static uint32_t cpsr_n, cpsr_z, cpsr_c, cpsr_v;
static uint32_t tls_val = 0;
static uint32_t fake_time_ms = 1000;
static uint32_t cgame_addr = 0;
static uint32_t audio_wrapper_addr = 0;
static uint32_t trainer_god_mode = 0;

// Minimal standalone C memory/string helpers (no libc required)
static void *my_memset(void *dst, int val, size_t n) {
    uint8_t *d = (uint8_t *)dst;
    uint8_t v = (uint8_t)val;
    for (size_t i = 0; i < n; i++) d[i] = v;
    return dst;
}

static void *my_memcpy(void *dst, const void *src, size_t n) {
    uint8_t *d = (uint8_t *)dst;
    const uint8_t *s = (const uint8_t *)src;
    for (size_t i = 0; i < n; i++) d[i] = s[i];
    return dst;
}

static void *my_memmove(void *dst, const void *src, size_t n) {
    uint8_t *d = (uint8_t *)dst;
    const uint8_t *s = (const uint8_t *)src;
    if (d < s || d >= s + n) {
        for (size_t i = 0; i < n; i++) d[i] = s[i];
    } else if (d > s) {
        for (size_t i = n; i > 0; i--) d[i - 1] = s[i - 1];
    }
    return dst;
}

static int my_memcmp(const void *a, const void *b, size_t n) {
    const uint8_t *pa = (const uint8_t *)a;
    const uint8_t *pb = (const uint8_t *)b;
    for (size_t i = 0; i < n; i++) {
        if (pa[i] != pb[i]) return (int)pa[i] - (int)pb[i];
    }
    return 0;
}

static uint8_t *my_memchr(const void *s, int c, size_t n) {
    const uint8_t *p = (const uint8_t *)s;
    uint8_t ch = (uint8_t)c;
    for (size_t i = 0; i < n; i++) {
        if (p[i] == ch) return (uint8_t *)(p + i);
    }
    return NULL;
}

static size_t my_strlen(const char *s) {
    size_t len = 0;
    while (s[len]) len++;
    return len;
}

static char *my_strcpy(char *dst, const char *src) {
    char *d = dst;
    while ((*d++ = *src++) != 0) {}
    return dst;
}

static char *my_strcat(char *dst, const char *src) {
    char *d = dst + my_strlen(dst);
    while ((*d++ = *src++) != 0) {}
    return dst;
}

static int my_strcmp(const char *a, const char *b) {
    while (*a && (*a == *b)) { a++; b++; }
    return (int)(uint8_t)*a - (int)(uint8_t)*b;
}

static int my_contains(const char *haystack, const char *needle) {
    size_t nl = my_strlen(needle);
    if (nl == 0) return 1;
    for (; *haystack; haystack++) {
        size_t i = 0;
        while (i < nl && haystack[i] == needle[i]) i++;
        if (i == nl) return 1;
    }
    return 0;
}

// Guest memory accessors (little-endian)
static inline uint32_t r32(uint32_t addr) {
    uint32_t a = (addr & ADDR_MASK) & ~3u;
    uint32_t val = (uint32_t)mem[a] | ((uint32_t)mem[a + 1] << 8) | ((uint32_t)mem[a + 2] << 16) | ((uint32_t)mem[a + 3] << 24);
    uint32_t rot = (addr & 3u) * 8;
    if (rot) val = (val >> rot) | (val << (32 - rot));
    return val;
}

static inline uint16_t r16(uint32_t addr) {
    uint32_t a = (addr & ADDR_MASK) & ~1u;
    return (uint16_t)mem[a] | ((uint16_t)mem[a + 1] << 8);
}

static inline uint8_t r8(uint32_t addr) {
    return mem[addr & ADDR_MASK];
}

static inline void w32(uint32_t addr, uint32_t val) {
    uint32_t a = (addr & ADDR_MASK) & ~3u;
    mem[a] = (uint8_t)(val & 0xff);
    mem[a + 1] = (uint8_t)((val >> 8) & 0xff);
    mem[a + 2] = (uint8_t)((val >> 16) & 0xff);
    mem[a + 3] = (uint8_t)((val >> 24) & 0xff);
}

static inline void w16(uint32_t addr, uint16_t val) {
    uint32_t a = (addr & ADDR_MASK) & ~1u;
    mem[a] = (uint8_t)(val & 0xff);
    mem[a + 1] = (uint8_t)((val >> 8) & 0xff);
}

static inline void w8(uint32_t addr, uint8_t val) {
    mem[addr & ADDR_MASK] = val;
}

// Coalescing Free-List Heap Allocator in Guest Memory
// Block header at `block_addr` (16-byte aligned):
//   [block_addr + 0]: uint32_t size (including 16-byte header)
//   [block_addr + 4]: uint32_t is_free (1 = free, 0 = allocated)
//   [block_addr + 8]: uint32_t magic (0xA110CA7E)
//   Payload starts at `block_addr + 16`.
static void heap_init(void) {
    uint32_t total = HEAP_END_ADDR - HEAP_START_ADDR;
    w32(HEAP_START_ADDR + 0, total);
    w32(HEAP_START_ADDR + 4, 1);
    w32(HEAP_START_ADDR + 8, 0xA110CA7Eu);
    w32(HEAP_START_ADDR + 12, 0);
}

static uint32_t guest_malloc(uint32_t req_size) {
    if (req_size == 0) req_size = 4;
    uint32_t needed = ((req_size + 15u) & ~15u) + 16u;
    uint32_t cur = HEAP_START_ADDR;
    while (cur < HEAP_END_ADDR) {
        uint32_t bsize = r32(cur);
        uint32_t is_free = r32(cur + 4);
        if (bsize == 0 || cur + bsize > HEAP_END_ADDR) break;
        if (is_free) {
            // Coalesce adjacent free blocks
            while (cur + bsize < HEAP_END_ADDR) {
                uint32_t next = cur + bsize;
                uint32_t nsize = r32(next);
                uint32_t nfree = r32(next + 4);
                if (nsize > 0 && nfree == 1 && next + nsize <= HEAP_END_ADDR) {
                    bsize += nsize;
                    w32(cur, bsize);
                } else {
                    break;
                }
            }
            if (bsize >= needed) {
                if (bsize >= needed + 32u) {
                    uint32_t rem = bsize - needed;
                    uint32_t next = cur + needed;
                    w32(next + 0, rem);
                    w32(next + 4, 1);
                    w32(next + 8, 0xA110CA7Eu);
                    w32(next + 12, 0);
                    w32(cur + 0, needed);
                }
                w32(cur + 4, 0);
                w32(cur + 8, 0xA110CA7Eu);
                uint32_t payload = cur + 16u;
                my_memset(mem + (payload & ADDR_MASK), 0, needed - 16u);
                return payload;
            }
        }
        cur += bsize;
    }
    return 0;
}

static void guest_free(uint32_t payload_addr) {
    if (payload_addr < HEAP_START_ADDR + 16u || payload_addr >= HEAP_END_ADDR) return;
    uint32_t hdr = payload_addr - 16u;
    if (r32(hdr + 8) == 0xA110CA7Eu) {
        w32(hdr + 4, 1);
    }
}

static int format_int(char *out, int32_t val, int width, int zero_pad) {
    char rev[16];
    int neg = 0;
    uint32_t u;
    if (val < 0) {
        neg = 1;
        u = (uint32_t)(-(val + 1)) + 1u;
    } else {
        u = (uint32_t)val;
    }
    int len = 0;
    if (u == 0) {
        rev[len++] = '0';
    } else {
        while (u > 0) {
            rev[len++] = (char)('0' + (u % 10u));
            u /= 10u;
        }
    }
    int total = len + neg;
    int pos = 0;
    if (!zero_pad) {
        while (width > total) { out[pos++] = ' '; width--; }
    }
    if (neg) out[pos++] = '-';
    if (zero_pad) {
        while (width > total) { out[pos++] = '0'; width--; }
    }
    for (int i = len - 1; i >= 0; i--) {
        out[pos++] = rev[i];
    }
    return pos;
}

static void guest_vsprintf(char *dst, const char *fmt, uint32_t *args) {
    int arg_idx = 0;
    while (*fmt) {
        if (*fmt != '%') {
            *dst++ = *fmt++;
            continue;
        }
        fmt++;
        if (*fmt == '%') {
            *dst++ = *fmt++;
            continue;
        }
        int zero_pad = 0;
        int width = 0;
        if (*fmt == '0') {
            zero_pad = 1;
            fmt++;
        }
        while (*fmt >= '0' && *fmt <= '9') {
            width = width * 10 + (*fmt - '0');
            fmt++;
        }
        char spec = *fmt ? *fmt++ : 0;
        uint32_t val = args[arg_idx++];
        if (spec == 's') {
            const char *str = (const char *)(mem + (val & ADDR_MASK));
            int slen = (int)my_strlen(str);
            while (width > slen) { *dst++ = ' '; width--; }
            my_memcpy(dst, str, (size_t)slen);
            dst += slen;
        } else if (spec == 'd' || spec == 'i' || spec == 'u') {
            dst += format_int(dst, (int32_t)val, width, zero_pad);
        } else if (spec == 'c') {
            *dst++ = (char)(val & 0xff);
        }
    }
    *dst = '\0';
}

static inline int check_cond(uint32_t cond) {
    switch (cond) {
        case 0x0: return cpsr_z;
        case 0x1: return !cpsr_z;
        case 0x2: return cpsr_c;
        case 0x3: return !cpsr_c;
        case 0x4: return cpsr_n;
        case 0x5: return !cpsr_n;
        case 0x6: return cpsr_v;
        case 0x7: return !cpsr_v;
        case 0x8: return cpsr_c && !cpsr_z;
        case 0x9: return !cpsr_c || cpsr_z;
        case 0xa: return cpsr_n == cpsr_v;
        case 0xb: return cpsr_n != cpsr_v;
        case 0xc: return !cpsr_z && (cpsr_n == cpsr_v);
        case 0xd: return cpsr_z || (cpsr_n != cpsr_v);
        case 0xe: return 1;
        default: return 1;
    }
}

static inline uint32_t get_reg(int r, uint32_t pc_val) {
    return (r == 15) ? pc_val : reg[r];
}

static uint32_t eval_shifter(uint32_t insn, uint32_t *carry_out, uint32_t pc_val) {
    if (insn & (1u << 25)) {
        uint32_t imm = insn & 0xffu;
        uint32_t rot = ((insn >> 8) & 0xfu) * 2u;
        if (rot == 0) {
            *carry_out = cpsr_c;
            return imm;
        }
        uint32_t val = (imm >> rot) | (imm << (32u - rot));
        *carry_out = (val >> 31) & 1u;
        return val;
    } else {
        int rm = (int)(insn & 0xfu);
        uint32_t val = get_reg(rm, pc_val);
        int shift_type = (int)((insn >> 5) & 3u);
        uint32_t shift_amt;
        if (insn & (1u << 4)) {
            int rs = (int)((insn >> 8) & 0xfu);
            shift_amt = reg[rs] & 0xffu;
            if (rm == 15) val += 4u;
            if (shift_amt == 0) {
                *carry_out = cpsr_c;
                return val;
            }
        } else {
            shift_amt = (insn >> 7) & 0x1fu;
        }
        switch (shift_type) {
            case 0:
                if (shift_amt == 0) { *carry_out = cpsr_c; return val; }
                if (shift_amt < 32) { *carry_out = (val >> (32u - shift_amt)) & 1u; return val << shift_amt; }
                if (shift_amt == 32) { *carry_out = val & 1u; return 0; }
                *carry_out = 0; return 0;
            case 1:
                if (shift_amt == 0) shift_amt = 32;
                if (shift_amt < 32) { *carry_out = (val >> (shift_amt - 1u)) & 1u; return val >> shift_amt; }
                if (shift_amt == 32) { *carry_out = (val >> 31) & 1u; return 0; }
                *carry_out = 0; return 0;
            case 2:
                if (shift_amt == 0) shift_amt = 32;
                if (shift_amt < 32) { *carry_out = (val >> (shift_amt - 1u)) & 1u; return (uint32_t)(((int32_t)val) >> shift_amt); }
                *carry_out = (val >> 31) & 1u;
                return (val & 0x80000000u) ? 0xffffffffu : 0;
            case 3:
                if (shift_amt == 0) {
                    *carry_out = val & 1u;
                    return (cpsr_c << 31) | (val >> 1);
                }
                shift_amt &= 31u;
                if (shift_amt == 0) { *carry_out = (val >> 31) & 1u; return val; }
                val = (val >> shift_amt) | (val << (32u - shift_amt));
                *carry_out = (val >> 31) & 1u;
                return val;
        }
    }
    return 0;
}

static void run_arm(uint32_t start_pc) {
    uint32_t saved_lr = reg[14];
    reg[14] = 0xdeadbee0u;
    reg[15] = start_pc;
    uint32_t steps = 0;
    while (reg[15] != 0xdeadbee0u) {
        if (++steps > 500000000u) break;
        uint32_t pc = reg[15];

        if (pc == 0x10007310u) { // High-quality interpolated + saturated channel mixer
            uint32_t chan = reg[0];
            uint32_t dst_pcm = reg[1];
            uint32_t num_samples = reg[2];
            int32_t master_vol = (int32_t)reg[3];
            uint32_t sample_obj = r32(chan);
            if (sample_obj != 0) {
                int32_t chan_vol = (int32_t)(int8_t)r8(chan + 0x3du);
                int32_t vol = (master_vol * chan_vol) >> 8;
                uint32_t sample_data = r32(sample_obj + 0x1cu);
                uint32_t loop_flag = r32(chan + 0x28u);
                uint32_t end_pos = (loop_flag != 0) ? r32(chan + 0x30u) : r32(chan + 0x40u);
                uint32_t loop_start = r32(chan + 0x2cu);
                uint32_t end_fp = end_pos << 16;
                uint32_t pos = r32(chan + 0x48u);
                uint32_t step = r32(chan + 0x4cu);
                for (uint32_t i = 0; i < num_samples; i++) {
                    if (pos > end_fp) {
                        if (loop_flag != 1u) {
                            w32(chan, 0);
                            w32(chan + 4u, 0);
                            break;
                        }
                        pos = pos - end_fp + (loop_start << 16);
                    }
                    uint32_t idx0 = pos >> 16;
                    uint32_t frac = pos & 0xffffu;
                    uint32_t idx1 = (idx0 + 1u < end_pos) ? (idx0 + 1u) : ((loop_flag == 1u) ? loop_start : idx0);
                    int32_t s0 = (int32_t)(int8_t)r8(sample_data + idx0);
                    int32_t s1 = (int32_t)(int8_t)r8(sample_data + idx1);
                    int32_t s_interp = s0 + (((s1 - s0) * (int32_t)frac) >> 16);
                    int32_t cur = (int32_t)(int16_t)r16(dst_pcm);
                    int32_t mixed = cur + ((s_interp * vol * 3) >> 2); // slight headroom to prevent multi-channel clipping
                    if (mixed > 32767) mixed = 32767;
                    else if (mixed < -32768) mixed = -32768;
                    w16(dst_pcm, (uint16_t)(int16_t)mixed);
                    dst_pcm += 2u;
                    pos += step;
                }
                if (r32(chan) != 0) w32(chan + 0x48u, pos);
            }
            reg[15] = reg[14]; continue;
        }

        if (pc == 0x10004378u || pc == 0x10004388u) { // 16.16 fixed-point multiply
            int64_t prod = (int64_t)(int32_t)reg[0] * (int64_t)(int32_t)reg[1];
            reg[0] = (uint32_t)(prod >> 16);
            reg[15] = reg[14]; continue;
        }

        if (pc >= 0x10041e00u || pc < 0x10014ff0u) {
            if (pc == 0x10013f9cu) {
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041e18u) {
                tls_val = reg[0];
                reg[0] = 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041e28u) {
                reg[0] = tls_val;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000b894u) {
                reg[0] = 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000b86cu) {
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000b97cu) {
                const char *fn = (const char *)(mem + (reg[1] & ADDR_MASK));
                if (my_contains(fn, "data.pak")) reg[0] = pak_size;
                else if (my_contains(fn, "game.cfg")) reg[0] = game_cfg_size;
                else reg[0] = 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000bae8u) {
                uint32_t self = reg[0];
                const char *fn = (const char *)(mem + (reg[1] & ADDR_MASK));
                uint8_t *dst = mem + (reg[2] & ADDR_MASK);
                uint32_t off = reg[3];
                uint32_t len = r32(reg[13]);
                uint8_t xor_key = r8(self);
                if (my_contains(fn, "data.pak")) {
                    if (off + len <= pak_size) my_memcpy(dst, pak_data + off, len);
                } else if (my_contains(fn, "game.cfg")) {
                    if (off + len <= game_cfg_size) my_memcpy(dst, game_cfg + off, len);
                }
                if (xor_key != 0) {
                    for (uint32_t i = 0; i < len; i++) dst[i] ^= xor_key;
                }
                reg[0] = 1;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000bc0cu) {
                uint32_t self = reg[0];
                const char *fn = (const char *)(mem + (reg[1] & ADDR_MASK));
                const uint8_t *src = mem + (reg[2] & ADDR_MASK);
                uint32_t off = reg[3];
                uint32_t len = r32(reg[13]);
                uint8_t xor_key = r8(self);
                if (my_contains(fn, "game.cfg") && off + len <= CFG_MAX_SIZE) {
                    for (uint32_t i = 0; i < len; i++) game_cfg[off + i] = src[i] ^ xor_key;
                    if (off + len > game_cfg_size) game_cfg_size = off + len;
                    game_cfg_dirty = 1;
                }
                reg[0] = 1;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10014fe0u) {
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000a478u) {
                w32(reg[0] + 4, 0);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1000a490u || pc == 0x1000a818u || pc == 0x1000a5ecu) {
                reg[0] = 0;
                reg[15] = reg[14]; continue;
            }
        }

        if (pc >= 0x10025b00u) {
            if (pc == 0x1002c0c0u) { // Fast 8x8 4bpp opaque tile blit
                uint32_t dst = reg[0];
                uint32_t src = reg[1];
                uint32_t pal = reg[2];
                for (int y = 0; y < 8; y++) {
                    uint32_t w = r32(src);
                    src += 4u;
                    for (int x = 0; x < 8; x++) {
                        uint32_t idx = (w >> (x * 4)) & 0xfu;
                        w16(dst + (uint32_t)(x * 2), r16(pal + idx * 2u));
                    }
                    dst += 0x180u;
                }
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10026758u) {
                audio_wrapper_addr = reg[0];
                w32(reg[0] + 0x1c, 768);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10026914u) {
                reg[0] = 16000;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1002686cu) {
                audio_wrapper_addr = reg[0];
                w32(reg[0] + 0x1c, 768);
                reg[0] = 1;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10026804u) {
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1002693cu) {
                reg[0] = 1;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10026b98u) {
                my_memset(mem + ((reg[0] + 0x20) & ADDR_MASK), 0, 768 * 2);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10026af0u) {
                my_memcpy(pcm_out, mem + ((reg[0] + 0x20) & ADDR_MASK), 768 * 2);
                reg[0] = 1;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x100269bcu || pc == 0x10026a88u || pc == 0x10026944u || pc == 0x10025b10u) {
                reg[0] = 1;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004239cu || pc == 0x1004207cu || pc == 0x1004216cu || pc == 0x1004224cu || pc == 0x1004228cu || pc == 0x1004206cu || pc == 0x1002ad98u || pc == 0x1002ae2cu) {
                reg[0] = guest_malloc(reg[0]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f4cu || pc == 0x1004227cu || pc == 0x1002ae28u || pc == 0x1002ae4cu || pc == 0x100423bcu) {
                guest_free(reg[0]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f7cu || pc == 0x10041f6cu || pc == 0x10041f8cu || pc == 0x100422ccu) {
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041e9cu) {
                my_memset(mem + (reg[0] & ADDR_MASK), (int)(reg[1] & 0xff), reg[2]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f5cu) {
                my_memset(mem + (reg[0] & ADDR_MASK), 0, reg[1]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004225cu) {
                my_memset(mem + (reg[0] & ADDR_MASK), (int)(reg[2] & 0xff), reg[1]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004217cu || pc == 0x10041efcu || pc == 0x100421dcu) {
                my_memmove(mem + (reg[0] & ADDR_MASK), mem + (reg[1] & ADDR_MASK), reg[2]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f0cu) {
                uint8_t *p = my_memchr(mem + (reg[0] & ADDR_MASK), (int)(reg[1] & 0xff), reg[2]);
                reg[0] = p ? (0x10000000u + (uint32_t)(p - mem)) : 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f1cu) {
                reg[0] = (uint32_t)my_memcmp(mem + (reg[0] & ADDR_MASK), mem + (reg[1] & ADDR_MASK), reg[2]);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f2cu) {
                my_strcpy((char *)(mem + (reg[0] & ADDR_MASK)), (const char *)(mem + (reg[1] & ADDR_MASK)));
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041eacu) {
                my_strcat((char *)(mem + (reg[0] & ADDR_MASK)), (const char *)(mem + (reg[1] & ADDR_MASK)));
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041edcu) {
                reg[0] = (uint32_t)my_strcmp((const char *)(mem + (reg[0] & ADDR_MASK)), (const char *)(mem + (reg[1] & ADDR_MASK)));
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041eecu) {
                reg[0] = (uint32_t)my_strlen((const char *)(mem + (reg[0] & ADDR_MASK)));
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041ebcu) {
                uint32_t args[8];
                args[0] = reg[2];
                args[1] = reg[3];
                for (int i = 0; i < 6; i++) args[2 + i] = r32(reg[13] + (uint32_t)(i * 4));
                guest_vsprintf((char *)(mem + (reg[0] & ADDR_MASK)), (const char *)(mem + (reg[1] & ADDR_MASK)), args);
                reg[0] = (uint32_t)my_strlen((const char *)(mem + (reg[0] & ADDR_MASK)));
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041eccu) {
                uint32_t args[8];
                for (int i = 0; i < 8; i++) args[i] = r32(reg[2] + (uint32_t)(i * 4));
                guest_vsprintf((char *)(mem + (reg[0] & ADDR_MASK)), (const char *)(mem + (reg[1] & ADDR_MASK)), args);
                reg[0] = (uint32_t)my_strlen((const char *)(mem + (reg[0] & ADDR_MASK)));
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041f3cu) {
                uint32_t base_addr = reg[0];
                uint32_t nmemb = reg[1];
                uint32_t size = reg[2];
                uint32_t compar = reg[3];
                uint8_t tmp[128];
                if (size <= sizeof(tmp)) {
                    for (uint32_t i = 1; i < nmemb; i++) {
                        uint32_t j = i;
                        while (j > 0) {
                            uint32_t a = base_addr + (j - 1) * size;
                            uint32_t b = base_addr + j * size;
                            uint32_t saved_r[16];
                            my_memcpy(saved_r, reg, sizeof(saved_r));
                            reg[0] = a; reg[1] = b;
                            run_arm(compar);
                            int32_t cmp_res = (int32_t)reg[0];
                            my_memcpy(reg, saved_r, sizeof(saved_r));
                            if (cmp_res <= 0) break;
                            my_memcpy(tmp, mem + (a & ADDR_MASK), size);
                            my_memcpy(mem + (a & ADDR_MASK), mem + (b & ADDR_MASK), size);
                            my_memcpy(mem + (b & ADDR_MASK), tmp, size);
                            j--;
                        }
                    }
                }
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004226cu) {
                fake_time_ms += 16;
                reg[0] = fake_time_ms;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10042cecu) {
                w32(reg[1], 0x101fb3ddu); // Nokia 6600 standard keypad (5 = Bomb, 8 = Detonate)
                reg[0] = 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10042c6cu || pc == 0x10042c7cu) {
                reg[0] = 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10042c8cu) {
                reg[0] = FB_GUEST_ADDR;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004236cu) {
                float f = (float)(int32_t)reg[0];
                my_memcpy(&reg[0], &f, 4);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004237cu) {
                float a, b, c;
                my_memcpy(&a, &reg[0], 4);
                my_memcpy(&b, &reg[1], 4);
                c = a + b;
                my_memcpy(&reg[0], &c, 4);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004238cu) { // __divsf3 (float / float: Amiga clock / sample_rate)
                float a, b, c;
                my_memcpy(&a, &reg[0], 4);
                my_memcpy(&b, &reg[1], 4);
                c = (b != 0.0f) ? (a / b) : 0.0f;
                my_memcpy(&reg[0], &c, 4);
                reg[15] = reg[14]; continue;
            } else if (pc == 0x10041e70u) {
                float f;
                my_memcpy(&f, &reg[0], 4);
                reg[0] = (uint32_t)(int32_t)f;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004235cu) {
                reg[0] = (reg[1] != 0) ? (reg[0] / reg[1]) : 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x100421ecu) {
                reg[0] = (reg[1] != 0) ? (uint32_t)((int32_t)reg[0] / (int32_t)reg[1]) : 0;
                reg[15] = reg[14]; continue;
            } else if (pc == 0x1004223cu) {
                reg[0] = (reg[1] != 0) ? (reg[0] % reg[1]) : 0;
                reg[15] = reg[14]; continue;
            }
        }

        uint32_t insn = r32(pc);
        reg[15] = pc + 4u;
        uint32_t cond = insn >> 28;
        if (!check_cond(cond)) continue;

        uint32_t pc8 = pc + 8u;

        if ((insn & 0x0ffffff0u) == 0x012fff10u) {
            int rm = (int)(insn & 0xfu);
            reg[15] = reg[rm] & ~1u;
            continue;
        }
        if ((insn & 0x0e000000u) == 0x0a000000u) {
            int link = (int)((insn >> 24) & 1u);
            int32_t imm24 = (int32_t)(insn << 8) >> 6;
            if (link) reg[14] = pc + 4u;
            reg[15] = (uint32_t)((int32_t)pc8 + imm24);
            continue;
        }
        if ((insn & 0x0f8000f0u) == 0x00800090u) {
            int u_signed = (int)((insn >> 22) & 1u);
            int accumulate = (int)((insn >> 21) & 1u);
            int s = (int)((insn >> 20) & 1u);
            int rdhi = (int)((insn >> 16) & 0xfu);
            int rdlo = (int)((insn >> 12) & 0xfu);
            int rs = (int)((insn >> 8) & 0xfu);
            int rm = (int)(insn & 0xfu);
            uint64_t res;
            if (u_signed) res = (uint64_t)((int64_t)(int32_t)reg[rm] * (int64_t)(int32_t)reg[rs]);
            else res = (uint64_t)reg[rm] * (uint64_t)reg[rs];
            if (accumulate) {
                uint64_t acc = ((uint64_t)reg[rdhi] << 32) | reg[rdlo];
                res += acc;
            }
            reg[rdlo] = (uint32_t)res;
            reg[rdhi] = (uint32_t)(res >> 32);
            if (s) { cpsr_n = (reg[rdhi] >> 31) & 1u; cpsr_z = (res == 0); }
            continue;
        }
        if ((insn & 0x0f8000f0u) == 0x00000090u) {
            int accumulate = (int)((insn >> 21) & 1u);
            int s = (int)((insn >> 20) & 1u);
            int rd = (int)((insn >> 16) & 0xfu);
            int rn = (int)((insn >> 12) & 0xfu);
            int rs = (int)((insn >> 8) & 0xfu);
            int rm = (int)(insn & 0xfu);
            uint32_t res = reg[rm] * reg[rs];
            if (accumulate) res += reg[rn];
            reg[rd] = res;
            if (s) { cpsr_n = (res >> 31) & 1u; cpsr_z = (res == 0); }
            continue;
        }
        if ((insn & 0x0e000090u) == 0x00000090u && ((insn & 0x60u) != 0)) {
            int p = (int)((insn >> 24) & 1u);
            int u = (int)((insn >> 23) & 1u);
            int i_bit = (int)((insn >> 22) & 1u);
            int w = (int)((insn >> 21) & 1u);
            int l = (int)((insn >> 20) & 1u);
            int rn = (int)((insn >> 16) & 0xfu);
            int rd = (int)((insn >> 12) & 0xfu);
            int sh = (int)((insn >> 5) & 3u);
            uint32_t off = i_bit ? (((insn >> 4) & 0xf0u) | (insn & 0xfu)) : reg[insn & 0xfu];
            uint32_t base = get_reg(rn, pc8);
            uint32_t addr = p ? (u ? base + off : base - off) : base;
            if (l) {
                if (sh == 1) reg[rd] = r16(addr);
                else if (sh == 2) reg[rd] = (uint32_t)(int32_t)(int8_t)r8(addr);
                else if (sh == 3) reg[rd] = (uint32_t)(int32_t)(int16_t)r16(addr);
            } else {
                if (sh == 1) w16(addr, (uint16_t)reg[rd]);
            }
            if (!p) addr = u ? base + off : base - off;
            if ((!p || w) && !(l && rn == rd)) reg[rn] = addr;
            continue;
        }
        if ((insn & 0x0c000000u) == 0x00000000u) {
            int opcode = (int)((insn >> 21) & 0xfu);
            int s = (int)((insn >> 20) & 1u);
            int rn = (int)((insn >> 16) & 0xfu);
            int rd = (int)((insn >> 12) & 0xfu);
            uint32_t shifter_c = cpsr_c;
            uint32_t op2 = eval_shifter(insn, &shifter_c, pc8);
            uint32_t op1 = get_reg(rn, pc8);
            uint32_t res = 0;
            int write_rd = 1;
            int arith = 0;
            uint64_t tmp64;
            switch (opcode) {
                case 0x0: res = op1 & op2; break;
                case 0x1: res = op1 ^ op2; break;
                case 0x2:
                    arith = 1; res = op1 - op2;
                    if (s) {
                        cpsr_c = (op1 >= op2);
                        cpsr_v = (((op1 ^ op2) & (op1 ^ res)) >> 31) & 1u;
                    }
                    break;
                case 0x3:
                    arith = 1; res = op2 - op1;
                    if (s) {
                        cpsr_c = (op2 >= op1);
                        cpsr_v = (((op2 ^ op1) & (op2 ^ res)) >> 31) & 1u;
                    }
                    break;
                case 0x4:
                    arith = 1; tmp64 = (uint64_t)op1 + (uint64_t)op2; res = (uint32_t)tmp64;
                    if (s) {
                        cpsr_c = (uint32_t)((tmp64 >> 32) & 1u);
                        cpsr_v = ((~(op1 ^ op2) & (op1 ^ res)) >> 31) & 1u;
                    }
                    break;
                case 0x5:
                    arith = 1; tmp64 = (uint64_t)op1 + (uint64_t)op2 + cpsr_c; res = (uint32_t)tmp64;
                    if (s) {
                        cpsr_c = (uint32_t)((tmp64 >> 32) & 1u);
                        cpsr_v = ((~(op1 ^ op2) & (op1 ^ res)) >> 31) & 1u;
                    }
                    break;
                case 0x6:
                    arith = 1; tmp64 = (uint64_t)op1 - (uint64_t)op2 - (1u - cpsr_c); res = (uint32_t)tmp64;
                    if (s) {
                        cpsr_c = (op1 >= (uint64_t)op2 + (1u - cpsr_c));
                        cpsr_v = (((op1 ^ op2) & (op1 ^ res)) >> 31) & 1u;
                    }
                    break;
                case 0x7:
                    arith = 1; tmp64 = (uint64_t)op2 - (uint64_t)op1 - (1u - cpsr_c); res = (uint32_t)tmp64;
                    if (s) {
                        cpsr_c = (op2 >= (uint64_t)op1 + (1u - cpsr_c));
                        cpsr_v = (((op2 ^ op1) & (op2 ^ res)) >> 31) & 1u;
                    }
                    break;
                case 0x8: res = op1 & op2; write_rd = 0; break;
                case 0x9: res = op1 ^ op2; write_rd = 0; break;
                case 0xa:
                    arith = 1; write_rd = 0; res = op1 - op2;
                    cpsr_c = (op1 >= op2);
                    cpsr_v = (((op1 ^ op2) & (op1 ^ res)) >> 31) & 1u;
                    break;
                case 0xb:
                    arith = 1; write_rd = 0; tmp64 = (uint64_t)op1 + (uint64_t)op2; res = (uint32_t)tmp64;
                    cpsr_c = (uint32_t)((tmp64 >> 32) & 1u);
                    cpsr_v = ((~(op1 ^ op2) & (op1 ^ res)) >> 31) & 1u;
                    break;
                case 0xc: res = op1 | op2; break;
                case 0xd: res = op2; break;
                case 0xe: res = op1 & ~op2; break;
                case 0xf: res = ~op2; break;
            }
            if (s && rd != 15) {
                if (!arith) cpsr_c = shifter_c;
                cpsr_z = (res == 0);
                cpsr_n = (res >> 31) & 1u;
            }
            if (write_rd) reg[rd] = res;
            continue;
        }
        if ((insn & 0x0c000000u) == 0x04000000u) {
            int i_bit = (int)((insn >> 25) & 1u);
            int p = (int)((insn >> 24) & 1u);
            int u = (int)((insn >> 23) & 1u);
            int b = (int)((insn >> 22) & 1u);
            int w = (int)((insn >> 21) & 1u);
            int l = (int)((insn >> 20) & 1u);
            int rn = (int)((insn >> 16) & 0xfu);
            int rd = (int)((insn >> 12) & 0xfu);
            uint32_t off;
            if (!i_bit) {
                off = insn & 0xfffu;
            } else {
                uint32_t dummy_c = cpsr_c;
                off = eval_shifter(insn & ~(1u << 25), &dummy_c, pc8);
            }
            uint32_t base = get_reg(rn, pc8);
            uint32_t addr = p ? (u ? base + off : base - off) : base;
            if (l) {
                uint32_t val = b ? r8(addr) : r32(addr);
                if (!p) addr = u ? base + off : base - off;
                if ((!p || w) && rn != rd) reg[rn] = addr;
                reg[rd] = val;
            } else {
                uint32_t val = get_reg(rd, pc + 12u);
                if (b) w8(addr, (uint8_t)val);
                else w32(addr, val);
                if (!p) addr = u ? base + off : base - off;
                if (!p || w) reg[rn] = addr;
            }
            continue;
        }
        if ((insn & 0x0e000000u) == 0x08000000u) {
            int p = (int)((insn >> 24) & 1u);
            int u = (int)((insn >> 23) & 1u);
            int w = (int)((insn >> 21) & 1u);
            int l = (int)((insn >> 20) & 1u);
            int rn = (int)((insn >> 16) & 0xfu);
            uint32_t rlist = insn & 0xffffu;
            int count = 0;
            for (int i = 0; i < 16; i++) if (rlist & (1u << i)) count++;
            uint32_t base = reg[rn];
            uint32_t addr;
            if (u) {
                addr = p ? base + 4u : base;
            } else {
                addr = p ? base - (uint32_t)(count * 4) : base - (uint32_t)(count * 4) + 4u;
            }
            uint32_t wb_addr = u ? base + (uint32_t)(count * 4) : base - (uint32_t)(count * 4);
            for (int i = 0; i < 16; i++) {
                if (rlist & (1u << i)) {
                    if (l) reg[i] = r32(addr);
                    else w32(addr, reg[i]);
                    addr += 4u;
                }
            }
            if (w && !(l && (rlist & (1u << rn)))) reg[rn] = wb_addr;
            continue;
        }
    }
    reg[14] = saved_lr;
}

static inline uint32_t color_dist(uint32_t c1, uint32_t c2) {
    if (c1 == c2) return 0;
    int r1 = (int)(c1 & 0xff), g1 = (int)((c1 >> 8) & 0xff), b1 = (int)((c1 >> 16) & 0xff);
    int r2 = (int)(c2 & 0xff), g2 = (int)((c2 >> 8) & 0xff), b2 = (int)((c2 >> 16) & 0xff);
    int dr = r1 - r2; if (dr < 0) dr = -dr;
    int dg = g1 - g2; if (dg < 0) dg = -dg;
    int db = b1 - b2; if (db < 0) db = -db;
    return (uint32_t)(dr * 3 + dg * 4 + db * 2);
}

static inline uint32_t color_mix(uint32_t c1, uint32_t c2) {
    if (c1 == c2) return c1;
    uint32_t rb = (((c1 & 0x00ff00ffu) + (c2 & 0x00ff00ffu)) >> 1) & 0x00ff00ffu;
    uint32_t g  = (((c1 & 0x0000ff00u) + (c2 & 0x0000ff00u)) >> 1) & 0x0000ff00u;
    return 0xff000000u | rb | g;
}

static inline uint32_t color_mix3(uint32_t center, uint32_t a, uint32_t b) {
    uint32_t m = color_mix(a, b);
    return color_mix(center, m);
}

static void run_epx_pass(const uint32_t *src, int sw, int sh, uint32_t *dst, int smooth) {
    int dw = sw * 2;
    uint32_t thresh = smooth ? 96u : 1u;
    for (int y = 0; y < sh; y++) {
        int ym1 = (y > 0) ? (y - 1) : 0;
        int yp1 = (y + 1 < sh) ? (y + 1) : (sh - 1);
        const uint32_t *row_u = src + ym1 * sw;
        const uint32_t *row_c = src + y * sw;
        const uint32_t *row_d = src + yp1 * sw;
        uint32_t *out0 = dst + (y * 2) * dw;
        uint32_t *out1 = dst + (y * 2 + 1) * dw;
        for (int x = 0; x < sw; x++) {
            int xm1 = (x > 0) ? (x - 1) : 0;
            int xp1 = (x + 1 < sw) ? (x + 1) : (sw - 1);
            uint32_t P = row_c[x];
            uint32_t A = row_u[x];
            uint32_t B = row_c[xp1];
            uint32_t C = row_c[xm1];
            uint32_t D = row_d[x];

            uint32_t E0 = P, E1 = P, E2 = P, E3 = P;
            int cd_diff = (color_dist(C, B) >= thresh);
            int ad_diff = (color_dist(A, D) >= thresh);

            if (cd_diff && ad_diff) {
                if (color_dist(C, A) < thresh) {
                    E0 = smooth ? color_mix3(P, C, A) : C;
                }
                if (color_dist(A, B) < thresh) {
                    E1 = smooth ? color_mix3(P, A, B) : B;
                }
                if (color_dist(C, D) < thresh) {
                    E2 = smooth ? color_mix3(P, C, D) : C;
                }
                if (color_dist(D, B) < thresh) {
                    E3 = smooth ? color_mix3(P, D, B) : B;
                }
            } else if (smooth) {
                if (color_dist(P, A) < 48u && color_dist(P, C) < 48u) E0 = color_mix3(P, A, C);
                if (color_dist(P, A) < 48u && color_dist(P, B) < 48u) E1 = color_mix3(P, A, B);
                if (color_dist(P, D) < 48u && color_dist(P, C) < 48u) E2 = color_mix3(P, D, C);
                if (color_dist(P, D) < 48u && color_dist(P, B) < 48u) E3 = color_mix3(P, D, B);
            }

            out0[x * 2]     = E0;
            out0[x * 2 + 1] = E1;
            out1[x * 2]     = E2;
            out1[x * 2 + 1] = E3;
        }
    }
}

static inline int iabs_val(int x) { return x < 0 ? -x : x; }

static inline uint32_t yuv_dist_int(uint32_t c1, uint32_t c2) {
    if (c1 == c2) return 0;
    int r1 = (int)(c1 & 0xffu), g1 = (int)((c1 >> 8) & 0xffu), b1 = (int)((c1 >> 16) & 0xffu);
    int r2 = (int)(c2 & 0xffu), g2 = (int)((c2 >> 8) & 0xffu), b2 = (int)((c2 >> 16) & 0xffu);
    int dr = r1 - r2, dg = g1 - g2, db = b1 - b2;
    int dy = iabs_val(3 * dr + 6 * dg + db);
    return (uint32_t)(dy + (iabs_val(dr) + iabs_val(dg) + iabs_val(db)) * 2);
}

static inline uint32_t lerp_rgb_int(uint32_t c1, uint32_t c2, uint32_t w2) {
    if (c1 == c2 || w2 == 0) return c1;
    if (w2 >= 256u) return c2;
    uint32_t w1 = 256u - w2;
    uint32_t rb = (((c1 & 0x00ff00ffu) * w1 + (c2 & 0x00ff00ffu) * w2 + 0x00800080u) >> 8) & 0x00ff00ffu;
    uint32_t g  = (((c1 & 0x0000ff00u) * w1 + (c2 & 0x0000ff00u) * w2 + 0x00008000u) >> 8) & 0x0000ff00u;
    return 0xff000000u | rb | g;
}

static inline uint32_t avg_rgb2(uint32_t c1, uint32_t c2) {
    uint32_t rb = (((c1 & 0x00ff00ffu) + (c2 & 0x00ff00ffu)) >> 1) & 0x00ff00ffu;
    uint32_t g  = (((c1 & 0x0000ff00u) + (c2 & 0x0000ff00u)) >> 1) & 0x0000ff00u;
    return 0xff000000u | rb | g;
}

// Stage 1: Edge-Preserving Bilateral De-Dithering (removes 4-bit/8-bit Symbian checkerboard dithering)
static void pass1_dedither_int(const uint32_t *src, uint32_t *dst, int w, int h) {
    const int thresh = 460;
    for (int y = 0; y < h; y++) {
        int ym1 = (y > 0) ? (y - 1) : 0;
        int yp1 = (y + 1 < h) ? (y + 1) : (h - 1);
        for (int x = 0; x < w; x++) {
            uint32_t center = src[y * w + x];
            int rc = (int)(center & 0xffu);
            int gc = (int)((center >> 8) & 0xffu);
            int bc = (int)((center >> 16) & 0xffu);

            int sum_r = rc * 640, sum_g = gc * 640, sum_b = bc * 640;
            int sum_w = 640;

            for (int dy = -1; dy <= 1; dy++) {
                int ny = (dy < 0) ? ym1 : ((dy > 0) ? yp1 : y);
                const uint32_t *nrow = src + ny * w;
                for (int dx = -1; dx <= 1; dx++) {
                    if (dx == 0 && dy == 0) continue;
                    int nx = x + dx;
                    if (nx < 0) nx = 0; else if (nx >= w) nx = w - 1;
                    uint32_t nb = nrow[nx];
                    int d = (int)yuv_dist_int(center, nb);
                    if (d < thresh) {
                        int diff = thresh - d;
                        int w_range = (diff * diff) >> 10;
                        int w_spatial = (dx == 0 || dy == 0) ? 4 : 3;
                        int wt = (w_range * w_spatial) >> 2;
                        sum_r += (int)(nb & 0xffu) * wt;
                        sum_g += (int)((nb >> 8) & 0xffu) * wt;
                        sum_b += (int)((nb >> 16) & 0xffu) * wt;
                        sum_w += wt;
                    }
                }
            }
            uint32_t r = (uint32_t)((sum_r + (sum_w >> 1)) / sum_w);
            uint32_t g = (uint32_t)((sum_g + (sum_w >> 1)) / sum_w);
            uint32_t b = (uint32_t)((sum_b + (sum_w >> 1)) / sum_w);
            dst[y * w + x] = 0xff000000u | (b << 16) | (g << 8) | r;
        }
    }
}

static inline uint32_t px_at(const uint32_t *img, int w, int h, int x, int y) {
    if (x < 0) x = 0; else if (x >= w) x = w - 1;
    if (y < 0) y = 0; else if (y >= h) y = h - 1;
    return img[y * w + x];
}

// Stage 2 & 4: Full 5x5 21-Tap xBR Level-2 2x Upscaler (45, 26.5, and 63.4 degree slope reconstruction)
static void xbr_2x_pass_int(const uint32_t *src, int sw, int sh, uint32_t *dst) {
    int dw = sw * 2;
    for (int y = 0; y < sh; y++) {
        for (int x = 0; x < sw; x++) {
            uint32_t A1 = px_at(src, sw, sh, x - 1, y - 2);
            uint32_t B1 = px_at(src, sw, sh, x,     y - 2);
            uint32_t C1 = px_at(src, sw, sh, x + 1, y - 2);

            uint32_t A0 = px_at(src, sw, sh, x - 2, y - 1);
            uint32_t A  = px_at(src, sw, sh, x - 1, y - 1);
            uint32_t B  = px_at(src, sw, sh, x,     y - 1);
            uint32_t C  = px_at(src, sw, sh, x + 1, y - 1);
            uint32_t C4 = px_at(src, sw, sh, x + 2, y - 1);

            uint32_t D0 = px_at(src, sw, sh, x - 2, y);
            uint32_t D  = px_at(src, sw, sh, x - 1, y);
            uint32_t E  = px_at(src, sw, sh, x,     y);
            uint32_t F  = px_at(src, sw, sh, x + 1, y);
            uint32_t F4 = px_at(src, sw, sh, x + 2, y);

            uint32_t G0 = px_at(src, sw, sh, x - 2, y + 1);
            uint32_t G  = px_at(src, sw, sh, x - 1, y + 1);
            uint32_t H  = px_at(src, sw, sh, x,     y + 1);
            uint32_t I  = px_at(src, sw, sh, x + 1, y + 1);
            uint32_t I4 = px_at(src, sw, sh, x + 2, y + 1);

            uint32_t G5 = px_at(src, sw, sh, x - 1, y + 2);
            uint32_t H5 = px_at(src, sw, sh, x,     y + 2);
            uint32_t I5 = px_at(src, sw, sh, x + 1, y + 2);

            uint32_t E0 = E, E1 = E, E2 = E, E3 = E;

            {
                uint32_t wd1 = yuv_dist_int(E, C) + yuv_dist_int(E, G) + yuv_dist_int(I, H5) + yuv_dist_int(I, F4) + 4u * yuv_dist_int(H, F);
                uint32_t wd2 = yuv_dist_int(H, D) + yuv_dist_int(H, I5) + yuv_dist_int(F, I4) + yuv_dist_int(F, B) + 4u * yuv_dist_int(E, I);
                if (wd1 < wd2) {
                    uint32_t nc = (yuv_dist_int(E, F) <= yuv_dist_int(E, H)) ? F : H;
                    uint32_t df = yuv_dist_int(F, G), dh = yuv_dist_int(H, C);
                    if ((df * 2u < dh && yuv_dist_int(E, G) > 140u) || (dh * 2u < df && yuv_dist_int(E, C) > 140u))
                        E3 = lerp_rgb_int(E, nc, 192u);
                    else
                        E3 = avg_rgb2(E, nc);
                }
            }
            {
                uint32_t wd1 = yuv_dist_int(E, A) + yuv_dist_int(E, I) + yuv_dist_int(G, H5) + yuv_dist_int(G, D0) + 4u * yuv_dist_int(D, H);
                uint32_t wd2 = yuv_dist_int(H, F) + yuv_dist_int(H, G5) + yuv_dist_int(D, G0) + yuv_dist_int(D, B) + 4u * yuv_dist_int(E, G);
                if (wd1 < wd2) {
                    uint32_t nc = (yuv_dist_int(E, D) <= yuv_dist_int(E, H)) ? D : H;
                    uint32_t dd = yuv_dist_int(D, I), dh = yuv_dist_int(H, A);
                    if ((dd * 2u < dh && yuv_dist_int(E, I) > 140u) || (dh * 2u < dd && yuv_dist_int(E, A) > 140u))
                        E2 = lerp_rgb_int(E, nc, 192u);
                    else
                        E2 = avg_rgb2(E, nc);
                }
            }
            {
                uint32_t wd1 = yuv_dist_int(E, A) + yuv_dist_int(E, I) + yuv_dist_int(C, B1) + yuv_dist_int(C, F4) + 4u * yuv_dist_int(B, F);
                uint32_t wd2 = yuv_dist_int(B, D) + yuv_dist_int(B, C1) + yuv_dist_int(F, C4) + yuv_dist_int(F, H) + 4u * yuv_dist_int(E, C);
                if (wd1 < wd2) {
                    uint32_t nc = (yuv_dist_int(E, F) <= yuv_dist_int(E, B)) ? F : B;
                    uint32_t df = yuv_dist_int(F, A), db = yuv_dist_int(B, I);
                    if ((df * 2u < db && yuv_dist_int(E, A) > 140u) || (db * 2u < df && yuv_dist_int(E, I) > 140u))
                        E1 = lerp_rgb_int(E, nc, 192u);
                    else
                        E1 = avg_rgb2(E, nc);
                }
            }
            {
                uint32_t wd1 = yuv_dist_int(E, G) + yuv_dist_int(E, C) + yuv_dist_int(A, B1) + yuv_dist_int(A, D0) + 4u * yuv_dist_int(D, B);
                uint32_t wd2 = yuv_dist_int(B, F) + yuv_dist_int(B, A1) + yuv_dist_int(D, A0) + yuv_dist_int(D, H) + 4u * yuv_dist_int(E, A);
                if (wd1 < wd2) {
                    uint32_t nc = (yuv_dist_int(E, D) <= yuv_dist_int(E, B)) ? D : B;
                    uint32_t dd = yuv_dist_int(D, C), db = yuv_dist_int(B, G);
                    if ((dd * 2u < db && yuv_dist_int(E, C) > 140u) || (db * 2u < dd && yuv_dist_int(E, G) > 140u))
                        E0 = lerp_rgb_int(E, nc, 192u);
                    else
                        E0 = avg_rgb2(E, nc);
                }
            }

            dst[(y * 2) * dw + (x * 2)]         = E0;
            dst[(y * 2) * dw + (x * 2 + 1)]     = E1;
            dst[(y * 2 + 1) * dw + (x * 2)]     = E2;
            dst[(y * 2 + 1) * dw + (x * 2 + 1)] = E3;
        }
    }
}

// Stage 3 & 5: Anime4K Directional Push + Sobel Iso-Contour Tangent Smoothing
static void anime4k_refine_int(const uint32_t *src, int w, int h, uint32_t *dst, uint32_t push_w) {
    int total = w * h;
    for (int i = 0; i < total; i++) {
        uint32_t c = src[i];
        luma_buf[i] = (uint16_t)((c & 0xffu) * 3u + ((c >> 8) & 0xffu) * 6u + ((c >> 16) & 0xffu));
    }

    for (int y = 0; y < h; y++) {
        if (y == 0 || y == h - 1) {
            for (int x = 0; x < w; x++) dst[y * w + x] = src[y * w + x];
            continue;
        }
        const uint32_t *s_u = src + (y - 1) * w;
        const uint32_t *s_c = src + y * w;
        const uint32_t *s_d = src + (y + 1) * w;
        const uint16_t *l_u = luma_buf + (y - 1) * w;
        const uint16_t *l_c = luma_buf + y * w;
        const uint16_t *l_d = luma_buf + (y + 1) * w;
        uint32_t *out = dst + y * w;

        out[0] = s_c[0];
        out[w - 1] = s_c[w - 1];

        for (int x = 1; x < w - 1; x++) {
            uint32_t tl = s_u[x - 1], tc = s_u[x], tr = s_u[x + 1];
            uint32_t ml = s_c[x - 1], mc = s_c[x], mr = s_c[x + 1];
            uint32_t bl = s_d[x - 1], bc = s_d[x], br = s_d[x + 1];

            int l_tl = l_u[x - 1], l_tc = l_u[x], l_tr = l_u[x + 1];
            int l_ml = l_c[x - 1], l_mc = l_c[x], l_mr = l_c[x + 1];
            int l_bl = l_d[x - 1], l_bc = l_d[x], l_br = l_d[x + 1];

            uint32_t res = mc;

            int min_u = l_bl < l_bc ? l_bl : l_bc; if (l_br < min_u) min_u = l_br;
            if (min_u > l_mc) {
                res = lerp_rgb_int(res, avg_rgb2(bc, avg_rgb2(bl, br)), push_w);
            } else {
                int max_u = l_bl > l_bc ? l_bl : l_bc; if (l_br > max_u) max_u = l_br;
                int min_d = l_tl < l_tc ? l_tl : l_tc; if (l_tr < min_d) min_d = l_tr;
                if (min_d > l_mc && l_mc >= max_u) {
                    res = lerp_rgb_int(res, avg_rgb2(tc, avg_rgb2(tl, tr)), push_w);
                }
            }

            int min_r = l_tr < l_mr ? l_tr : l_mr; if (l_br < min_r) min_r = l_br;
            if (min_r > l_mc) {
                res = lerp_rgb_int(res, avg_rgb2(mr, avg_rgb2(tr, br)), push_w);
            } else {
                int min_l = l_tl < l_ml ? l_tl : l_ml; if (l_bl < min_l) min_l = l_bl;
                if (min_l > l_mc) {
                    res = lerp_rgb_int(res, avg_rgb2(ml, avg_rgb2(tl, bl)), push_w);
                }
            }

            int gx = (l_tr + 2 * l_mr + l_br) - (l_tl + 2 * l_ml + l_bl);
            int gy = (l_bl + 2 * l_bc + l_br) - (l_tl + 2 * l_tc + l_tr);
            int agx = iabs_val(gx), agy = iabs_val(gy);
            if (agx + agy > 100) {
                int tx = 0, ty = 0;
                if (agy * 2 > agx) tx = (-gy > 0) ? 1 : -1;
                if (agx * 2 > agy) ty = (gx > 0) ? 1 : -1;
                uint32_t cp = src[(y + ty) * w + (x + tx)];
                uint32_t cm = src[(y - ty) * w + (x - tx)];
                uint32_t tang_avg = avg_rgb2(cp, cm);
                if (yuv_dist_int(res, tang_avg) < 500u) {
                    res = lerp_rgb_int(res, tang_avg, 115u);
                }
            }

            out[x] = res;
        }
    }
}

static void update_rgba_fb(void) {
    uint32_t base = FB_GUEST_ADDR & ADDR_MASK;
    int idx = 0;
    for (int y = 8; y < 8 + 208; y++) {
        uint32_t row_off = base + (uint32_t)(y * 192 * 2);
        for (int x = 8; x < 8 + 176; x++) {
            uint32_t p_off = row_off + (uint32_t)(x * 2);
            uint16_t px = (uint16_t)mem[p_off] | ((uint16_t)mem[p_off + 1] << 8);
            uint32_t r5 = (px >> 11) & 0x1fu;
            uint32_t g6 = (px >> 5) & 0x3fu;
            uint32_t b5 = px & 0x1fu;
            uint32_t r8_val = (r5 << 3) | (r5 >> 2);
            uint32_t g8_val = (g6 << 2) | (g6 >> 4);
            uint32_t b8_val = (b5 << 3) | (b5 >> 2);
            rgba_fb[idx++] = 0xff000000u | (b8_val << 16) | (g8_val << 8) | r8_val;
        }
    }
    if (upscale_mode == 0) {
        for (int y = 0; y < 208; y++) {
            const uint32_t *srow = rgba_fb + y * 176;
            for (int dy = 0; dy < 4; dy++) {
                uint32_t *drow = upscaled_4x + (y * 4 + dy) * 704;
                for (int x = 0; x < 176; x++) {
                    uint32_t c = srow[x];
                    drow[x * 4 + 0] = c;
                    drow[x * 4 + 1] = c;
                    drow[x * 4 + 2] = c;
                    drow[x * 4 + 3] = c;
                }
            }
        }
    } else if (upscale_mode == 1) {
        xbr_2x_pass_int(rgba_fb, 176, 208, upscaled_2x);
        xbr_2x_pass_int(upscaled_2x, 352, 416, upscaled_4x);
    } else {
        pass1_dedither_int(rgba_fb, dedith_1x, 176, 208);
        xbr_2x_pass_int(dedith_1x, 176, 208, upscaled_2x);
        anime4k_refine_int(upscaled_2x, 352, 416, refine_2x, 90u);
        xbr_2x_pass_int(refine_2x, 352, 416, xbr_4x);
        anime4k_refine_int(xbr_4x, 704, 832, upscaled_4x, 108u);
    }
}

WASM_EXPORT("vm_get_code_buf")
uint8_t *vm_get_code_buf(void) {
    return mem;
}

WASM_EXPORT("vm_get_pak_buf")
uint8_t *vm_get_pak_buf(void) {
    return pak_data;
}

WASM_EXPORT("vm_get_cfg_buf")
uint8_t *vm_get_cfg_buf(void) {
    return game_cfg;
}

WASM_EXPORT("vm_get_cfg_size")
uint32_t vm_get_cfg_size(void) {
    return game_cfg_size;
}

WASM_EXPORT("vm_consume_cfg_dirty")
uint32_t vm_consume_cfg_dirty(void) {
    uint32_t d = game_cfg_dirty;
    game_cfg_dirty = 0;
    return d;
}

WASM_EXPORT("vm_get_rgba_ptr")
uint32_t *vm_get_rgba_ptr(void) {
    return rgba_fb;
}

WASM_EXPORT("vm_get_upscaled_rgba_ptr")
uint32_t *vm_get_upscaled_rgba_ptr(void) {
    return upscaled_4x;
}

WASM_EXPORT("vm_set_upscale_mode")
void vm_set_upscale_mode(uint32_t mode) {
    upscale_mode = mode % 3u;
    update_rgba_fb();
}

WASM_EXPORT("vm_get_pcm_ptr")
int16_t *vm_get_pcm_ptr(void) {
    return pcm_out;
}

WASM_EXPORT("vm_init")
void vm_init(uint32_t pak_len, uint32_t cfg_len) {
    pak_size = pak_len;
    if (cfg_len > 0 && cfg_len <= CFG_MAX_SIZE) {
        game_cfg_size = cfg_len;
    } else {
        my_memset(game_cfg, 0, sizeof(game_cfg));
        my_strcpy((char *)game_cfg, "This is an empty configuration file.");
        game_cfg_size = 36;
    }
    game_cfg_dirty = 0;

    heap_init();
    my_memset(reg, 0, sizeof(reg));
    cpsr_n = cpsr_z = cpsr_c = cpsr_v = 0;
    fake_time_ms = 1000;
    reg[13] = STACK_TOP_ADDR;

    cgame_addr = guest_malloc(0x600);
    uint32_t cview = guest_malloc(0x100);
    w32(cview + 0x20, 0x0b); // EColor64K (16-bit RGB565)

    // 1. CGame::CGame()
    reg[0] = cgame_addr;
    run_arm(0x1000e524u);

    tls_val = cgame_addr;
    w32(cgame_addr + 0x350, cview);

    // 2. CGame::Init()
    reg[0] = cgame_addr;
    run_arm(0x1000f3b8u);

    // 3. CGame::Start()
    reg[0] = cgame_addr;
    run_arm(0x1000db98u);

    // 4. CGame::LoadMenu()
    reg[0] = cgame_addr;
    run_arm(0x1000f4fcu);

    // Snapshot initial 104-byte config state at cgame_addr + 4
    my_memcpy(last_cgame_cfg, mem + ((cgame_addr + 4u) & ADDR_MASK), 0x68);

    update_rgba_fb();
}

static void sync_cgame_cfg(void) {
    if (!cgame_addr) return;
    const uint8_t *cur_cfg = mem + ((cgame_addr + 4u) & ADDR_MASK);
    if (my_memcmp(cur_cfg, last_cgame_cfg, 0x68) != 0) {
        my_memcpy(last_cgame_cfg, cur_cfg, 0x68);
        for (uint32_t i = 0; i < 0x68u; i++) {
            game_cfg[i] = cur_cfg[i] ^ 0xaau;
        }
        game_cfg_size = 0x68u;
        game_cfg_dirty = 1;
    }
}

WASM_EXPORT("vm_force_save_cfg")
void vm_force_save_cfg(void) {
    if (!cgame_addr) return;
    const uint8_t *cur_cfg = mem + ((cgame_addr + 4u) & ADDR_MASK);
    my_memcpy(last_cgame_cfg, cur_cfg, 0x68);
    for (uint32_t i = 0; i < 0x68u; i++) {
        game_cfg[i] = cur_cfg[i] ^ 0xaau;
    }
    game_cfg_size = 0x68u;
    game_cfg_dirty = 1;
}

WASM_EXPORT("vm_tick")
void vm_tick(uint32_t dt_ms) {
    if (!cgame_addr) return;
    fake_time_ms += dt_ms;

    // Optional God Mode trainer enforcement on Player 1
    if (trainer_god_mode) {
        w8(cgame_addr + 4, 1); // IDRULEZ flag
        uint32_t p1 = r32(cgame_addr + 0x3ac);
        if (p1 >= 0x10000000u) {
            if (r8(p1 + 0x45) < 5) w8(p1 + 0x45, 5); // Lives = 5
        }
    }

    uint32_t gc = r32(cgame_addr + 0x88);
    if (gc) {
        reg[0] = gc;
        reg[1] = FB_GUEST_ADDR;
        run_arm(0x10008428u);
    }

    reg[0] = cgame_addr;
    run_arm(0x1000f544u);

    uint32_t inp = r32(cgame_addr + 0x8c);
    if (inp) {
        reg[0] = inp;
        run_arm(0x100134d0u);
    }

    sync_cgame_cfg();
    update_rgba_fb();
}

WASM_EXPORT("vm_key_event")
void vm_key_event(uint32_t scan_code, uint32_t pressed) {
    if (!cgame_addr) return;
    uint32_t inp = r32(cgame_addr + 0x8c);
    if (!inp) return;

    // Migrate old Nokia 3650 keymap (52/53) if loaded from cached game.cfg
    if (r8(inp + 8 + 0x0a) == 52 && r8(inp + 8 + 0x0b) == 53) {
        w8(inp + 8 + 0x0a, 53);
        w8(inp + 8 + 0x0b, 56);
        w8(cgame_addr + 0x54 + 0x0a, 53);
        w8(cgame_addr + 0x54 + 0x0b, 56);
    }

    // In active gameplay (not in menu and not in pause overlay), allow Enter/FIRE (167) to also place bombs
    if (scan_code == 167 && r8(cgame_addr + 0xa0) == 0 && r32(cgame_addr + 0xa4) == 0) {
        scan_code = r8(inp + 8 + 0x0a);
    }

    reg[0] = inp;
    reg[1] = scan_code;
    reg[2] = pressed ? 1u : 0u;
    run_arm(0x1001355cu);
}

WASM_EXPORT("vm_mix_audio")
void vm_mix_audio(void) {
    my_memset(pcm_out, 0, sizeof(pcm_out));
    if (!cgame_addr) return;
    uint32_t audio = r32(cgame_addr + 0xb0);
    if (!audio) return;
    reg[0] = audio;
    run_arm(0x10026f54u);
}

WASM_EXPORT("vm_play_sfx")
void vm_play_sfx(uint32_t sfx_idx) {
    if (!cgame_addr || sfx_idx > 14) return;
    uint32_t audio = r32(cgame_addr + 0xb0);
    uint32_t sfx_table = r32(cgame_addr + 0xbc);
    if (!audio || !sfx_table) return;
    uint32_t handle = r32(sfx_table + sfx_idx * 4u);
    reg[13] = STACK_TOP_ADDR;
    w32(reg[13], 0);
    w32(reg[13] + 4, 0);
    reg[0] = audio;
    reg[1] = handle;
    reg[2] = 1;
    reg[3] = 0x38;
    run_arm(0x100270acu);
}

WASM_EXPORT("vm_play_music_pos")
void vm_play_music_pos(uint32_t play_cmd, uint32_t pattern_pos) {
    if (!cgame_addr) return;
    uint32_t audio = r32(cgame_addr + 0xb0);
    if (!audio) return;
    reg[0] = audio;
    reg[1] = play_cmd;
    reg[2] = pattern_pos;
    run_arm(0x10026d54u);
}

// Apply built-in Explode Arena cheat codes or trainer perks:
// 1 = IDRULEZ (Unlock All / Invincibility)
// 2 = S.FORCE (Secret Sky Force maps)
// 3 = IDREAMS (Secret Infinite Dreams maps)
// 4..10 = ALIEN1..ALIEN7 (Play as Secret Alien character 1..7)
// 20 = Max Powerups (Bombs, Flame, Speed, Kick, Detonator for Player 1 in-game)
// 21 = Toggle Trainer God Mode
WASM_EXPORT("vm_get_state_info")
void vm_get_state_info(uint32_t *out_info) {
    out_info[0] = cgame_addr;
    out_info[1] = tls_val;
    out_info[2] = fake_time_ms;
    out_info[3] = audio_wrapper_addr;
    out_info[4] = trainer_god_mode;
    for (int i = 0; i < 16; i++) out_info[5 + i] = reg[i];
    out_info[21] = cpsr_n;
    out_info[22] = cpsr_z;
    out_info[23] = cpsr_c;
    out_info[24] = cpsr_v;
}

WASM_EXPORT("vm_set_state_info")
void vm_set_state_info(const uint32_t *in_info) {
    cgame_addr = in_info[0];
    tls_val = in_info[1];
    fake_time_ms = in_info[2];
    audio_wrapper_addr = in_info[3];
    trainer_god_mode = in_info[4];
    for (int i = 0; i < 16; i++) reg[i] = in_info[5 + i];
    cpsr_n = in_info[21];
    cpsr_z = in_info[22];
    cpsr_c = in_info[23];
    cpsr_v = in_info[24];
    if (cgame_addr) {
        my_memcpy(last_cgame_cfg, mem + ((cgame_addr + 4u) & ADDR_MASK), 0x68);
    }
    update_rgba_fb();
}

WASM_EXPORT("vm_apply_cheat")
void vm_apply_cheat(uint32_t cheat_id) {
    if (!cgame_addr) return;
    char *p1_name = (char *)(mem + ((cgame_addr + 0x28) & ADDR_MASK));
    if (cheat_id == 1) {
        my_strcpy(p1_name, "IDRULEZ");
        w8(cgame_addr + 4, 1);
    } else if (cheat_id == 2) {
        my_strcpy(p1_name, "S.FORCE");
        w8(cgame_addr + 0x374, 1);
    } else if (cheat_id == 3) {
        my_strcpy(p1_name, "IDREAMS");
        w8(cgame_addr + 0x374, 2);
    } else if (cheat_id >= 4 && cheat_id <= 10) {
        char buf[8] = "ALIEN1";
        buf[5] = (char)('0' + (cheat_id - 3));
        my_strcpy(p1_name, buf);
        w8(cgame_addr + 0x1c, (uint8_t)cheat_id);
    } else if (cheat_id == 20) {
        uint32_t p1 = r32(cgame_addr + 0x3ac);
        if (p1 >= 0x10000000u) {
            w8(p1 + 0x45, 9);   // Lives = 9
            w8(p1 + 0xf0, 5);   // Extra bombs
            w8(p1 + 0xf1, 5);   // Flame length
            w8(p1 + 0xf2, 1);   // Remote detonator
            w8(p1 + 0xf3, 1);   // Bomb kick
            w8(p1 + 0xf4, 2);   // Speed boost
        }
    } else if (cheat_id == 21) {
        trainer_god_mode = !trainer_god_mode;
        if (trainer_god_mode) w8(cgame_addr + 4, 1);
    }
}
