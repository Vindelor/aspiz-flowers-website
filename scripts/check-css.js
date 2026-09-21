#!/usr/bin/env node
/*
 * Fails (exit 1) if a hand-written stylesheet has unbalanced braces.
 *
 * Why this exists: a merge once left ".product-track { ... " without its
 * closing "}". Browsers do not report that as an error - they silently nest or
 * drop every rule that follows, so images collapsed to 0px and the site looked
 * "broken on the server" while everything still built fine. This makes that
 * kind of mistake fail the deploy instead of reaching visitors.
 *
 * Usage: node scripts/check-css.js [file ...]   (default: static/vendor/css/site.css)
 */
const fs = require("fs");

const files = process.argv.slice(2);
if (!files.length) files.push("static/vendor/css/site.css");

let failed = false;
for (const file of files) {
  const css = fs.readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  let depth = 0;
  let line = 1;
  for (const ch of css) {
    if (ch === "\n") line++;
    else if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth < 0) {
        console.error(`${file}: extra "}" near line ${line}`);
        failed = true;
        break;
      }
    }
  }
  if (!failed && depth !== 0) {
    console.error(`${file}: ${depth} unclosed "{" (a rule is missing its closing brace)`);
    failed = true;
  }
  if (!failed) console.log(`${file}: braces balanced`);
}
process.exit(failed ? 1 : 0);
