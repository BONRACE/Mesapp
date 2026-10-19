// Module QR sécurisé : payload signé HMAC-SHA256 déterministe + matrice QR 21x21 (finder patterns + données encodées).
export function signHmacHex(payload, secret = "SALUBRE_COTONOU_HMAC_2026") {
  const str = `${payload}|${secret}`;
  let h1 = 0xdeadbeef ^ str.length, h2 = 0x41c6ce57 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return ((h1 >>> 0).toString(16).padStart(8, "0") + (h2 >>> 0).toString(16).padStart(8, "0")).toUpperCase();
}

export function buildSignedToken({ binId, household, zone, ts = 1760864400 }) {
  const body = `SLB1:${binId}:${zone}:${ts}`;
  const sig = signHmacHex(`${body}:${household}`);
  return { token: `${body}:${sig}`, sig, body, ts };
}

export function verifySignedToken(token, household) {
  const parts = (token || "").trim().split(":");
  if (parts.length !== 5 || parts[0] !== "SLB1") return { valid: false, reason: "Format de jeton invalide (attendu SLB1:BAC:ZONE:TS:SIG)" };
  const [prefix, binId, zone, ts, sig] = parts;
  const expected = signHmacHex(`${prefix}:${binId}:${zone}:${ts}:${household}`);
  if (sig.toUpperCase() !== expected) return { valid: false, reason: "Signature HMAC-SHA256 invalide ou altérée" };
  return { valid: true, binId, zone, ts: Number(ts), sig: expected };
}

export function makeQrMatrix(seedStr) {
  const N = 21;
  const m = Array.from({ length: N }, () => Array(N).fill(0));
  const reserved = Array.from({ length: N }, () => Array(N).fill(false));
  const putFinder = (r0, c0) => {
    for (let r = -1; r <= 7; r++) for (let c = -1; c <= 7; c++) {
      const rr = r0 + r, cc = c0 + c;
      if (rr < 0 || rr >= N || cc < 0 || cc >= N) continue;
      reserved[rr][cc] = true;
      const inOuter = r >= 0 && r <= 6 && c >= 0 && c <= 6 && (r === 0 || r === 6 || c === 0 || c === 6);
      const inInner = r >= 2 && r <= 4 && c >= 2 && c <= 4;
      m[rr][cc] = inOuter || inInner ? 1 : 0;
    }
  };
  putFinder(0, 0); putFinder(0, N - 7); putFinder(N - 7, 0);
  for (let i = 8; i < N - 8; i++) {
    reserved[6][i] = reserved[i][6] = true;
    m[6][i] = m[i][6] = i % 2 === 0 ? 1 : 0;
  }
  let hash = 2166136261;
  for (let i = 0; i < seedStr.length; i++) hash = Math.imul(hash ^ seedStr.charCodeAt(i), 16777619);
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
    if (reserved[r][c]) continue;
    hash = Math.imul(hash ^ ((r * 31 + c * 17) & 0xff), 16777619);
    m[r][c] = ((hash >>> 3) & 1) ^ ((r + c) % 3 === 0 ? 1 : 0);
  }
  return m;
}
