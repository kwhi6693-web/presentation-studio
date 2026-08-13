#!/usr/bin/env node
import { createServer } from "node:http";
import { existsSync } from "node:fs";
import { access, mkdir } from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const HELP = `Usage: node scripts/export-pdf.mjs <input.html> [output.pdf] [--overwrite]\n\nExports a local HTML presentation with Playwright. No package is installed at runtime.`;

function parseArgs(argv) {
  if (argv.includes("--help") || argv.includes("-h")) return { help: true };
  const positional = argv.filter((value) => !value.startsWith("--"));
  if (!positional[0]) throw new Error(HELP);
  const input = path.resolve(positional[0]);
  const output = path.resolve(positional[1] ?? `${input.slice(0, -path.extname(input).length)}.pdf`);
  return { help: false, input, output, overwrite: argv.includes("--overwrite") };
}

function safeLocalPath(root, requestUrl) {
  const pathname = decodeURIComponent(new URL(requestUrl, "http://127.0.0.1").pathname);
  const relativeUrl = pathname.replace(/^[/\\]+/, "");
  const candidate = path.resolve(root, relativeUrl);
  const relative = path.relative(root, candidate);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return null;
  return candidate;
}

async function loadPlaywright() {
  const roots = [process.cwd(), ...String(process.env.NODE_PATH ?? "").split(path.delimiter).filter(Boolean)];
  for (const root of roots) {
    try {
      const req = createRequire(path.join(root, "package.json"));
      return await import(pathToFileURL(req.resolve("playwright")).href);
    } catch {
      // Try the next configured dependency root.
    }
  }
  throw new Error("Playwright is unavailable. Configure NODE_PATH or install it outside the read-only engine.");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(HELP);
    return 0;
  }
  await access(args.input);
  if (existsSync(args.output) && !args.overwrite) throw new Error(`Output exists: ${args.output}. Pass --overwrite to replace it.`);
  await mkdir(path.dirname(args.output), { recursive: true });
  const root = path.dirname(args.input);
  const entryName = path.basename(args.input);
  const server = createServer((req, res) => {
    const requested = req.url === "/" ? `/${entryName}` : req.url ?? "/";
    const file = safeLocalPath(root, requested);
    if (!file) {
      res.writeHead(403).end("Forbidden");
      return;
    }
    import("node:fs").then(({ createReadStream }) => {
      const stream = createReadStream(file);
      stream.on("error", () => res.writeHead(404).end("Not found"));
      stream.pipe(res);
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  let browser;
  try {
    const playwright = await loadPlaywright();
    browser = await playwright.chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle" });
    await page.emulateMedia({ media: "print" });
    await page.pdf({ path: args.output, printBackground: true, preferCSSPageSize: true });
    console.log(`Exported ${args.output}`);
    return 0;
  } finally {
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

main().then((code) => process.exitCode = code).catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
