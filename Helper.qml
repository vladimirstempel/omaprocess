import QtQuick
import Quickshell
import Quickshell.Io

// Runs bin/omaprocess. Everything that touches /proc or sends a signal lives
// there, so it can be tested and driven from a terminal with no shell running.
Item {
  id: root

  readonly property string cli: Qt.resolvedUrl("bin/omaprocess").toString().replace(/^file:\/\//, "")
  readonly property bool busy: listProc.running || actionProc.running

  signal snapshotReady(var snapshot)
  signal failed(string message)
  signal actionFinished(bool ok)

  function refresh() {
    if (!listProc.running) listProc.running = true
  }

  function run(args) {
    if (actionProc.running) return false
    actionProc.command = [root.cli].concat(args)
    actionProc.running = true
    return true
  }

  Process {
    id: listProc
    command: [root.cli, "list"]
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
    stderr: StdioCollector { id: actionErr; waitForEnd: true }
    onExited: function (exitCode) {
      if (exitCode !== 0) root.failed(String(actionErr.text || "").trim() || "Could not end it (" + exitCode + ")")
      root.actionFinished(exitCode === 0)
    }
  }
}
