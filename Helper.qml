import QtQuick
import Quickshell
import Quickshell.Io

// Runs bin/omaprocess. Everything that touches /proc or sends a signal lives
// there, so it can be tested and driven from a terminal with no shell running.
Item {
  id: root

  readonly property string cli: Qt.resolvedUrl("bin/omaprocess").toString().replace(/^file:\/\//, "")
  // Through the interpreter, not the file itself: a checkout without the
  // executable bit, or one on a noexec mount, must still work.
  readonly property var launcher: ["python3", root.cli]
  readonly property bool busy: listProc.running || actionProc.running

  signal snapshotReady(var snapshot)
  signal failed(string message)
  signal actionFinished(bool ok)

  function refresh() {
    if (listProc.running) return
    listProc.launched = false
    listProc.running = true
  }

  function run(args) {
    if (actionProc.running) return false
    actionProc.command = root.launcher.concat(args)
    actionProc.launched = false
    actionProc.running = true
    return true
  }

  Process {
    id: listProc
    // A process that never started exits with no code: say so, or the panel waits forever.
    property bool launched: false
    command: root.launcher.concat(["list"])
    onStarted: launched = true
    onRunningChanged: if (!running && !launched) root.failed("Could not run python3")
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (String(text || "") === "") return
        try {
          root.snapshotReady(JSON.parse(String(text || "")))
        } catch (e) {
          root.failed("Could not read process list")
        }
      }
    }
    stderr: StdioCollector { id: listErr; waitForEnd: true }
    onExited: function (exitCode) {
      if (exitCode !== 0) root.failed(String(listErr.text || "").trim() || "omaprocess list failed (" + exitCode + ")")
    }
  }

  Process {
    id: actionProc
    property bool launched: false
    onStarted: launched = true
    onRunningChanged: {
      if (running || launched) return
      root.failed("Could not run python3")
      root.actionFinished(false)
    }
    stderr: StdioCollector { id: actionErr; waitForEnd: true }
    onExited: function (exitCode) {
      if (exitCode !== 0) root.failed(String(actionErr.text || "").trim() || "Could not end it (" + exitCode + ")")
      root.actionFinished(exitCode === 0)
    }
  }
}
