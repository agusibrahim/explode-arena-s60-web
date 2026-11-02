/**
 * Symbian OS EPOC Release 6 (.sis) & Infinite Dreams data.pak Parser
 * Pure JavaScript — zero external dependencies, runs 100% client-side in the browser.
 */
(function (root) {
  "use strict";

  // Pure-JS RFC 1951 DEFLATE decompressor (for zlib streams inside Symbian .sis files)
  function inflateRaw(src, startOffset, expectedLen) {
    let pos = startOffset;
    let bitBuf = 0;
    let bitCnt = 0;

    function bits(n) {
      while (bitCnt < n) {
        bitBuf |= (src[pos++] || 0) << bitCnt;
        bitCnt += 8;
      }
      const val = bitBuf & ((1 << n) - 1);
      bitBuf >>>= n;
      bitCnt -= n;
      return val;
    }

    function buildTree(lengths) {
      const maxBits = 15;
      const counts = new Int32Array(maxBits + 1);
      for (let i = 0; i < lengths.length; i++) counts[lengths[i]]++;
      counts[0] = 0;
      const nextCode = new Int32Array(maxBits + 1);
      let code = 0;
      for (let b = 1; b <= maxBits; b++) {
        code = (code + counts[b - 1]) << 1;
        nextCode[b] = code;
      }
      const map = new Map();
      for (let sym = 0; sym < lengths.length; sym++) {
        const len = lengths[sym];
        if (len !== 0) {
          const c = nextCode[len]++;
          map.set((len << 16) | c, sym);
        }
      }
      return map;
    }

    function decodeSym(tree) {
      let code = 0;
      for (let len = 1; len <= 15; len++) {
        code = (code << 1) | bits(1);
        const sym = tree.get((len << 16) | code);
        if (sym !== undefined) return sym;
      }
      throw new Error("Invalid Huffman code in SIS zlib stream");
    }

    const fixedLitLen = new Uint8Array(288);
    for (let i = 0; i <= 143; i++) fixedLitLen[i] = 8;
    for (let i = 144; i <= 255; i++) fixedLitLen[i] = 9;
    for (let i = 256; i <= 279; i++) fixedLitLen[i] = 7;
    for (let i = 280; i <= 287; i++) fixedLitLen[i] = 8;
    const fixedDist = new Uint8Array(32);
    fixedDist.fill(5);

    const fixedLitTree = buildTree(fixedLitLen);
    const fixedDistTree = buildTree(fixedDist);

    const lenBase = [
      3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
      35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258
    ];
    const lenExtra = [
      0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
      3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0
    ];
    const distBase = [
      1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
      257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
      8193, 12289, 16385, 24577
    ];
    const distExtra = [
      0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
      7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13
    ];
    const clOrder = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

    const out = new Uint8Array(expectedLen);
    let outPos = 0;
    let bfinal = 0;

    while (!bfinal) {
      bfinal = bits(1);
      const btype = bits(2);
      if (btype === 0) {
        bitBuf = 0;
        bitCnt = 0;
        const len = src[pos] | (src[pos + 1] << 8);
        pos += 4;
        out.set(src.subarray(pos, pos + len), outPos);
        pos += len;
        outPos += len;
      } else if (btype === 1 || btype === 2) {
        let litTree = fixedLitTree;
        let distTree = fixedDistTree;
        if (btype === 2) {
          const hlit = bits(5) + 257;
          const hdist = bits(5) + 1;
          const hclen = bits(4) + 4;
          const clLengths = new Uint8Array(19);
          for (let i = 0; i < hclen; i++) clLengths[clOrder[i]] = bits(3);
          const clTree = buildTree(clLengths);
          const allLengths = new Uint8Array(hlit + hdist);
          let idx = 0;
          while (idx < hlit + hdist) {
            const s = decodeSym(clTree);
            if (s < 16) {
              allLengths[idx++] = s;
            } else if (s === 16) {
              const rep = bits(2) + 3;
              const prev = allLengths[idx - 1];
              for (let r = 0; r < rep; r++) allLengths[idx++] = prev;
            } else if (s === 17) {
              const rep = bits(3) + 3;
              for (let r = 0; r < rep; r++) allLengths[idx++] = 0;
            } else if (s === 18) {
              const rep = bits(7) + 11;
              for (let r = 0; r < rep; r++) allLengths[idx++] = 0;
            }
          }
          litTree = buildTree(allLengths.subarray(0, hlit));
          distTree = buildTree(allLengths.subarray(hlit));
        }

        while (true) {
          const sym = decodeSym(litTree);
          if (sym < 256) {
            out[outPos++] = sym;
          } else if (sym === 256) {
            break;
          } else {
            const lIdx = sym - 257;
            const length = lenBase[lIdx] + bits(lenExtra[lIdx]);
            const dSym = decodeSym(distTree);
            const dist = distBase[dSym] + bits(distExtra[dSym]);
            for (let k = 0; k < length; k++) {
              out[outPos] = out[outPos - dist];
              outPos++;
            }
          }
        }
      } else {
        throw new Error("Invalid DEFLATE block type 3");
      }
    }
    return out;
  }

  function decompressZlib(bytes, expectedLen) {
    // Skip 2-byte RFC 1950 zlib header (e.g., 0x78 0x9C)
    return inflateRaw(bytes, 2, expectedLen);
  }

  // Exact filename hash algorithm reverse-engineered from 0x1000c05c in ExplodeArena.app
  function computePakHash(name) {
    let h = 0x12345678;
    for (let i = 0; i < name.length; i++) {
      const ch = name.charCodeAt(i);
      const shift = (i & 3) * 8;
      const term = (Math.imul(i, ch) << shift) >>> 0;
      h = (h + term) >>> 0;
    }
    return h >>> 0;
  }

  function buildKnownHashLookup() {
    const candidates = [
      "loading.pic", "waiting.pic", "mask1.raw", "soundtrack.mod",
      "menu_move.wav", "menu_select.wav", "menu_abort.wav",
      "bomb_explode1.wav", "bomb_explode2.wav", "bomb_place.wav",
      "bonus.wav", "hero_respawn.wav", "girl_death.wav",
      "fatman_death.wav", "skater_death.wav", "worker_death.wav",
      "key_collect.wav", "door_open.wav", "alien_death.wav"
    ];
    for (const p of ["explode", "explodearena", "menu"]) {
      candidates.push(
        `${p}.lvltypes.dat`, `${p}.npp`, `${p}.nps`,
        `${p}.nps.and.dat`, `${p}.nps.anh.dat`, `${p}.nps.ans.dat`,
        `${p}.pals.dat`, `${p}.brk.dat`, `${p}.brk.pals.dat`, `${p}.msk.dat`
      );
      for (let n = 0; n < 50; n++) {
        const num = String(n).padStart(3, "0");
        candidates.push(`${p}.lvl${num}.dat`);
      }
    }
    const map = new Map();
    for (const c of candidates) {
      map.set(computePakHash(c), c);
    }
    return map;
  }

  function parseDataPakManifest(pakBytes) {
    const dv = new DataView(pakBytes.buffer, pakBytes.byteOffset, pakBytes.byteLength);
    const count = dv.getUint32(0x10, true);
    const dirBytes = new Uint8Array(count * 16);
    for (let i = 0; i < count * 16; i++) {
      dirBytes[i] = pakBytes[0x14 + i] ^ 0xaa;
    }
    const dirDv = new DataView(dirBytes.buffer);
    const hashMap = buildKnownHashLookup();
    const manifest = [];

    for (let i = 0; i < count; i++) {
      const h = dirDv.getUint32(i * 16 + 0, true);
      const off = dirDv.getUint32(i * 16 + 4, true);
      const usize = dirDv.getUint32(i * 16 + 8, true);
      const cflag = dirDv.getUint32(i * 16 + 12, true);
      const csize = cflag & 0x00ffffff;
      const ctype = cflag >>> 24;
      const name = hashMap.get(h) || `entry_${i}.bin`;
      const ext = name.split(".").pop();
      const cat =
        ext === "mod" ? "Audio (MOD)" :
        ext === "wav" ? "Audio (WAV)" :
        name.includes(".lvl") ? "Level / Menu Map" :
        "Sprite / Tile / Palette";

      manifest.push({
        index: i,
        name,
        hash: "0x" + h.toString(16).padStart(8, "0"),
        offset: "0x" + off.toString(16).padStart(6, "0"),
        compressedSize: csize,
        uncompressedSize: usize,
        compression: ctype === 2 ? "LZARI (Type 2)" : ctype === 3 ? "IMP! (Type 3)" : `Raw (Type ${ctype})`,
        category: cat
      });
    }
    return manifest;
  }

  function decodeUtf16LE(bytes, offset, byteLen) {
    let out = "";
    for (let i = 0; i < byteLen; i += 2) {
      out += String.fromCharCode(bytes[offset + i] | (bytes[offset + i + 1] << 8));
    }
    return out;
  }

  function parseSymbianSis(arrayBuffer) {
    const bytes = arrayBuffer instanceof Uint8Array ? arrayBuffer : new Uint8Array(arrayBuffer);
    if (bytes.byteLength < 0x68) {
      throw new Error("File is too small to be a valid Symbian .sis package.");
    }
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const uid1 = dv.getUint32(0x00, true);
    const uid2 = dv.getUint32(0x04, true);
    const uid3 = dv.getUint32(0x08, true);

    if (uid3 !== 0x10000419) {
      throw new Error(`Unsupported SIS format (UID3 = 0x${uid3.toString(16)}, expected Symbian EPOC Release 6 0x10000419).`);
    }

    const numLangs = dv.getUint16(0x12, true);
    const numFiles = dv.getUint16(0x14, true);
    const major = dv.getUint16(0x28, true);
    const minor = dv.getUint16(0x2a, true);
    const pfiles = dv.getUint32(0x34, true);
    const pname = dv.getUint32(0x40, true);

    let packageName = "ExplodeArena";
    if (numLangs > 0 && pname + 8 <= bytes.byteLength) {
      const nameLen = dv.getUint32(pname, true);
      const namePtr = dv.getUint32(pname + 4, true);
      if (namePtr + nameLen <= bytes.byteLength) {
        packageName = decodeUtf16LE(bytes, namePtr, nameLen);
      }
    }

    const sisFiles = [];
    let appBytes = null;
    let pakBytes = null;
    let cfgBytes = null;

    for (let i = 0; i < numFiles; i++) {
      const off = pfiles + i * 0x30;
      const dlen = dv.getUint32(off + 0x14, true);
      const dptr = dv.getUint32(off + 0x18, true);
      const flen = dv.getUint32(off + 0x1c, true);
      const fptr = dv.getUint32(off + 0x20, true);
      const ulen = dv.getUint32(off + 0x24, true);

      const destPath = decodeUtf16LE(bytes, dptr, dlen);
      const fileName = destPath.split("\\").pop();
      const compSlice = bytes.subarray(fptr, fptr + flen);
      const rawData = flen === ulen ? compSlice.slice() : decompressZlib(compSlice, ulen);

      sisFiles.push({
        index: i,
        destPath,
        fileName,
        compressedSize: flen,
        uncompressedSize: ulen,
        data: rawData
      });

      const lower = fileName.toLowerCase();
      if (lower.endsWith(".app")) appBytes = rawData;
      else if (lower === "data.pak") pakBytes = rawData;
      else if (lower === "game.cfg") cfgBytes = rawData;
    }

    if (!appBytes || !pakBytes) {
      throw new Error("Could not find ExplodeArena.app and data.pak inside the uploaded .sis archive.");
    }

    // Parse Symbian E32ImageHeader of ExplodeArena.app
    const appDv = new DataView(appBytes.buffer, appBytes.byteOffset, appBytes.byteLength);
    const sig = String.fromCharCode(appBytes[0x10], appBytes[0x11], appBytes[0x12], appBytes[0x13]);
    if (sig !== "EPOC") {
      throw new Error(`Invalid Symbian E32 executable signature "${sig}" (expected "EPOC").`);
    }
    const codeSize = appDv.getUint32(0x30, true);
    const codeBase = appDv.getUint32(0x4c, true);
    const codeOffset = appDv.getUint32(0x64, true);
    const codeBytes = appBytes.subarray(codeOffset, codeOffset + codeSize);

    const manifest = parseDataPakManifest(pakBytes);

    return {
      metadata: {
        packageName,
        uid1: "0x" + uid1.toString(16).padStart(8, "0"),
        uid2: "0x" + uid2.toString(16).padStart(8, "0"),
        version: `${major}.${minor}`,
        codeBase: "0x" + codeBase.toString(16).padStart(8, "0"),
        codeSize,
        pakSize: pakBytes.byteLength,
        numFiles
      },
      codeBytes,
      pakBytes,
      cfgBytes,
      manifest,
      sisFiles
    };
  }

  root.SymbianSisParser = {
    parseSymbianSis,
    computePakHash
  };
})(typeof window !== "undefined" ? window : globalThis);
