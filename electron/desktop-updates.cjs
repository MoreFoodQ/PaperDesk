// PaperDesk must never download or install an upstream EasyRead release.
function registerUpdates({ ipcMain, trustedWindow }) {
  const state = { supported: false, phase: "idle", version: "", percent: 0, error: "" };
  ipcMain.handle("easyread:update-state", event => { trustedWindow(event); return state; });
  for (const action of ["download", "install"]) {
    ipcMain.handle(`easyread:update-${action}`, async event => {
      trustedWindow(event);
      return state;
    });
  }
}
module.exports = { registerUpdates };
