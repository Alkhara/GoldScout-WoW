// Test helper for the admin dashboard's Cloudflare Access check
// (tests/test_server.py AdminTests): makes a throwaway RSA key and prints its
// public key set plus a few signed tokens, good and bad, as JSON.
import { generateKeyPairSync, createSign } from "node:crypto";

const { publicKey, privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const stranger = generateKeyPairSync("rsa", { modulusLength: 2048 }).privateKey;
const kid = "test-key-" + Date.now();
const jwk = { ...publicKey.export({ format: "jwk" }), kid, alg: "RS256", use: "sig" };
const now = Math.floor(Date.now() / 1000);

const b64 = (value) => Buffer.from(typeof value === "string" ? value : JSON.stringify(value)).toString("base64url");

function sign(claims, key = privateKey, keyId = kid) {
  const head = b64({ alg: "RS256", kid: keyId, typ: "JWT" }) + "." + b64(claims);
  return head + "." + createSign("RSA-SHA256").update(head).sign(key).toString("base64url");
}

const base = { aud: ["test-audience"], iss: "https://test.cloudflareaccess.com", email: "admin@example.com",
  sub: "test", iat: now, exp: now + 600 };
const good = sign(base);
const [h, p] = good.split(".");
console.log(JSON.stringify({
  jwks: { keys: [jwk] },
  tokens: {
    good,
    wrongAudience: sign({ ...base, aud: ["someone-else"] }),
    expired: sign({ ...base, exp: now - 30 }),
    wrongIssuer: sign({ ...base, iss: "https://other.cloudflareaccess.com" }),
    wrongKey: sign(base, stranger),
    unknownKey: sign(base, privateKey, "not-a-key"),
    tampered: h + "." + b64({ ...base, email: "intruder@example.com" }) + "." + good.split(".")[2],
    unsigned: h + "." + p + ".",
  },
}));
