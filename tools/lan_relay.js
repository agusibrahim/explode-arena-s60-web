#!/usr/bin/env node
/**
 * Explode Arena (Symbian S60) — Zero-Dependency Local Network (LAN) WebSocket Relay
 *
 * Bridges virtualized Symbian Bluetooth RFCOMM/L2CAP packets (CBTTransport)
 * between up to 4 browser clients on the same Wi-Fi / LAN / Hotspot.
 *
 * Usage (Node.js 18+ or Bun):
 *   node tools/lan_relay.js [port]
 *   bun tools/lan_relay.js [port]
 */

const http = require("http");
const crypto = require("crypto");
const os = require("os");

const PORT = parseInt(process.argv[2] || process.env.PORT || "8765", 10);
const clients = new Set();

function encodeWsFrame(payloadBuf, opcode = 0x02) {
  const len = payloadBuf.length;
  let header;
  if (len < 126) {
    header = Buffer.alloc(2);
    header[0] = 0x80 | opcode;
    header[1] = len;
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  return Buffer.concat([header, payloadBuf]);
}

const server = http.createServer((req, res) => {
  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end("Explode Arena S60 Bluetooth-over-LAN WebSocket Relay Active\n");
});

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) {
    socket.destroy();
    return;
  }
  const accept = crypto
    .createHash("sha1")
    .update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
    .digest("base64");

  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\n" +
      "Upgrade: websocket\r\n" +
      "Connection: Upgrade\r\n" +
      `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
  );
  socket.setNoDelay(true);
  clients.add(socket);

  let rxBuf = Buffer.alloc(0);
  socket.on("data", (chunk) => {
    rxBuf = Buffer.concat([rxBuf, chunk]);
    while (rxBuf.length >= 2) {
      const b0 = rxBuf[0];
      const b1 = rxBuf[1];
      const opcode = b0 & 0x0f;
      const masked = (b1 & 0x80) !== 0;
      let payloadLen = b1 & 0x7f;
      let offset = 2;

      if (payloadLen === 126) {
        if (rxBuf.length < 4) return;
        payloadLen = rxBuf.readUInt16BE(2);
        offset = 4;
      } else if (payloadLen === 127) {
        if (rxBuf.length < 10) return;
        payloadLen = Number(rxBuf.readBigUInt64BE(2));
        offset = 10;
      }

      const maskLen = masked ? 4 : 0;
      if (rxBuf.length < offset + maskLen + payloadLen) return;

      const payload = Buffer.from(
        rxBuf.subarray(offset + maskLen, offset + maskLen + payloadLen)
      );
      if (masked) {
        const mask = rxBuf.subarray(offset, offset + 4);
        for (let i = 0; i < payload.length; i++) {
          payload[i] ^= mask[i & 3];
        }
      }
      rxBuf = rxBuf.subarray(offset + maskLen + payloadLen);

      if (opcode === 0x08) {
        socket.end();
        return;
      }
      if (opcode === 0x09) {
        socket.write(encodeWsFrame(payload, 0x0a));
        continue;
      }
      if (opcode === 0x01 || opcode === 0x02) {
        const frame = encodeWsFrame(payload, opcode);
        for (const peer of clients) {
          if (peer !== socket && !peer.destroyed) {
            peer.write(frame);
          }
        }
      }
    }
  });

  const cleanup = () => clients.delete(socket);
  socket.on("close", cleanup);
  socket.on("error", cleanup);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log("==============================================================");
  console.log("  Explode Arena S60 — Bluetooth-over-LAN WebSocket Relay");
  console.log("==============================================================");
  const nets = os.networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      if (net.family === "IPv4" && !net.internal) {
        console.log(`  LAN Address : ws://${net.address}:${PORT}`);
      }
    }
  }
  console.log(`  Localhost   : ws://localhost:${PORT}`);
  console.log("==============================================================");
});
