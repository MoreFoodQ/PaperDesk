const { test } = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { registerUpdates } = require("../electron/desktop-updates.cjs");

function fixture() {
  const handlers = {};
  const updater = new EventEmitter();
  const calls = [];
  updater.setFeedURL = () => {};
  updater.checkForUpdates = async () => ({ isUpdateAvailable: true, updateInfo: { version: "1.3.2" } });
  updater.downloadUpdate = async () => { calls.push("download"); updater.emit("update-downloaded", { version: "1.3.2" }); };
  updater.quitAndInstall = (...args) => calls.push(["install", ...args]);
  registerUpdates({
    app: { isPackaged: true }, updater,
    ipcMain: { handle: (name, fn) => { handlers[name] = fn; } },
    trustedWindow: event => { if (event !== "trusted") throw Error("Untrusted"); },
    getWindow: () => null,
    prepareInstall: async () => { calls.push("shutdown"); },
    recover: async () => { calls.push("recover"); },
  });
  return { updater, calls, run: (name, event = "trusted") => handlers[`easyread:update-${name}`](event) };
}

test("fork cannot download or install upstream releases", async () => {
  const f = fixture();
  assert.equal((await f.run("state")).supported, false);
  assert.equal((await f.run("download")).phase, "idle");
  await f.run("install");
  assert.deepEqual(f.calls, []);
});

test("disabled update feature never calls network or installer", async () => {
  const f = fixture();
  const download = f.updater.downloadUpdate;
  f.updater.downloadUpdate = async () => { throw Error("offline"); };
  assert.equal((await f.run("download")).phase, "idle");
  f.updater.downloadUpdate = download;
  assert.equal((await f.run("download")).phase, "idle");
});

test("no available update does not download; install without download does nothing", async () => {
  const f = fixture();
  f.updater.checkForUpdates = async () => ({ isUpdateAvailable: false });
  await f.run("download");
  await f.run("install");
  assert.deepEqual(f.calls, []);
});

test("untrusted renderer cannot invoke update operations", async () => {
  const f = fixture();
  assert.throws(() => f.run("state", "foreign"), /Untrusted/);
  await assert.rejects(f.run("download", "foreign"), /Untrusted/);
  await assert.rejects(f.run("install", "foreign"), /Untrusted/);
});

test("concurrent download requests do not start downloads", async () => {
  const f = fixture();
  await Promise.all([f.run("download"), f.run("download")]);
  assert.deepEqual(f.calls, []);
});
