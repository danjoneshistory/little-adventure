#!/usr/bin/env node
// Downloads every hunt photo from the Cloudflare server into the photos/ folder as .jpg files,
// named after the spot they were taken at (e.g. "Pooh Sticks Bridge.jpg").
// Only reads from the server; it never changes or deletes anything.
//
//   node tools/get_photos.mjs           (from the project folder)
//   node tools/get_photos.mjs --local   (practice copy of the storage, for testing)
//
// Needs the Cloudflare login from "npx wrangler login".

import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const worker = join(root, "worker");
const out = join(root, "photos");
const where = process.argv.includes("--local") ? "--local" : "--remote";

function wrangler(...args){
  return execFileSync("npx", ["wrangler", "kv", "key", ...args, "--binding", "HUNT", where],
    { cwd: worker, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] });
}

// Spot names come from the HUNT config in index.html.
function spotNames(){
  const html = readFileSync(join(root, "index.html"), "utf8");
  const m = html.match(/const HUNT = (\{[\s\S]*?\n\});/);
  const names = {};
  if (!m) return names;
  try {
    const hunt = new Function("return " + m[1])();
    hunt.places.forEach((p, i) => {
      names["p" + i] = p.name;
      (p.choices || []).forEach((c, k) => { names[i + "-" + k] = c.name; });
    });
  } catch (e) {}
  return names;
}

const listing = wrangler("list", "--prefix", "photo:");
const keys = JSON.parse(listing.slice(listing.indexOf("["))).map(k => k.name);
if (!keys.length){ console.log("No photos on the server yet."); process.exit(0); }

const names = spotNames();
mkdirSync(out, { recursive: true });
for (const key of keys){
  const id = key.slice("photo:".length);
  const text = wrangler("get", key);
  const m = text.match(/data:image\/(\w+);base64,([A-Za-z0-9+/=]+)/);
  if (!m){ console.log("Skipped " + key + " (not a photo)"); continue; }
  const ext = m[1] === "jpeg" ? "jpg" : m[1];
  const file = join(out, (names[id] || id).replace(/[\/:]/g, "-") + "." + ext);
  writeFileSync(file, Buffer.from(m[2], "base64"));
  console.log("Saved " + file);
}
