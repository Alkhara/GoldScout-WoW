// Test helper for server/src/alerts.js (tests/test_alerts.py): reads
// {"fn": "findProblems" | "planAlerts", "args": [...]} as JSON on stdin and
// prints what the function returns, as JSON.
import { pathToFileURL } from "node:url";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const alerts = await import(pathToFileURL(resolve(here, "..", "server", "src", "alerts.js")).href);

let input = "";
for await (const chunk of process.stdin) {
  input += chunk;
}
const { fn, args } = JSON.parse(input);
process.stdout.write(JSON.stringify(alerts[fn](...args)));
