const { chromium } = require("playwright");
const { execFileSync } = require("child_process");

const SERVER = process.env.VAULTWARDEN_URL || "https://localhost:80";
const EMAIL = process.env.SEED_EMAIL || "demo@example.com";
const PASSWORD = process.env.SEED_PASSWORD || "SeedMasterPassw0rd!123";
const NAME = process.env.SEED_NAME || "Demo User";

const SAMPLE_ITEMS = [
  {
    name: "Example Service",
    username: "demo-user",
    password: "demo-pass-123",
    uri: "https://example.com",
  },
  {
    name: "Internal Wiki",
    username: "wiki-bot",
    password: "wiki-pass-456",
    uri: "https://wiki.internal.example",
  },
  {
    name: "Postgres (staging)",
    username: "app_user",
    password: "staging-db-pass-789",
    uri: "",
  },
];

function bw(args, opts = {}) {
  return execFileSync("bw", args, { encoding: "utf8", ...opts });
}

function tryLogin() {
  try {
    return bw(["login", EMAIL, PASSWORD, "--raw"]).trim();
  } catch {
    return null;
  }
}

function getStatus() {
  return JSON.parse(bw(["status"]));
}

async function registerAccount() {
  console.log(`Registering ${EMAIL} via the web vault...`);
  const browser = await chromium.launch();
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();

  await page.goto(`${SERVER}/#/signup`, { waitUntil: "networkidle" });
  await page.getByLabel("Email address").fill(EMAIL);
  await page.getByLabel("Name").fill(NAME);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForURL(/finish-signup/, { timeout: 15000 });

  await page
    .locator("#input-password-form_check-for-breaches")
    .uncheck()
    .catch(() => {});
  await page.locator("#input-password-form_new-password").fill(PASSWORD);
  await page
    .locator("#input-password-form_new-password-confirm")
    .fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForSelector("text=Your new account has been created", {
    timeout: 15000,
  });

  await browser.close();
  console.log("Account created.");
}

async function main() {
  const status = getStatus();
  let session;

  if (status.status === "unauthenticated") {
    bw(["config", "server", SERVER]);
    session = tryLogin();
    if (!session) {
      await registerAccount();
      session = tryLogin();
      if (!session) {
        throw new Error("Login failed even after registration");
      }
    } else {
      console.log(`Account ${EMAIL} already exists, skipping registration.`);
    }
  } else {
    console.log(
      `Account already configured (status: ${status.status}), unlocking...`,
    );
    session = bw(["unlock", PASSWORD, "--raw"]).trim();
  }

  const env = { ...process.env, BW_SESSION: session };
  bw(["sync"], { env });

  const existing = JSON.parse(bw(["list", "items"], { env }));
  const existingNames = new Set(existing.map((i) => i.name));

  for (const item of SAMPLE_ITEMS) {
    if (existingNames.has(item.name)) {
      console.log(`Item "${item.name}" already exists, skipping.`);
      continue;
    }
    const payload = {
      organizationId: null,
      folderId: null,
      type: 1,
      name: item.name,
      notes: null,
      login: {
        username: item.username,
        password: item.password,
        uris: item.uri ? [{ uri: item.uri }] : [],
      },
    };
    const encoded = bw(["encode"], { input: JSON.stringify(payload) }).trim();
    bw(["create", "item", encoded], { env });
    console.log(`Created item "${item.name}".`);
  }

  console.log("Seeding complete.");
}

main().catch((err) => {
  console.error("Seed failed:", err.message || err);
  process.exit(1);
});
