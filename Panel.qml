pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model
import "components"

// Bar button plus popup. The popup coordinates: it owns view state (query,
// expanded groups, cursor, pending terminations) and delegates I/O to Helper
// and every decision about rows to Model.js.
Panel {
  id: root
  moduleName: "omaprocess"
  ipcTarget: "omaprocess"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ apps: [], system: [] })
  property var expanded: ({})
  property bool systemOpen: false
  property string cursorId: ""
  property var pending: ({})
  property real now: Date.now()
  property string errorText: ""
  property var confirmRow: null
  property bool confirmForce: false

  readonly property var rows: Model.buildRows(root.snapshot, { query: search.text, expanded: root.expanded, systemOpen: root.systemOpen })
  readonly property int cursorIndex: Model.indexOfId(root.rows, root.cursorId)
  readonly property var cursorRow: root.cursorIndex >= 0 ? root.rows[root.cursorIndex] : null

  onOpenedChanged: {
    root.confirmRow = null
    if (!opened) return
    search.text = ""
    root.errorText = ""
    root.cursorId = ""
    helper.refresh()
  }

  function moveCursor(delta) {
    var index = Model.stepCursor(root.rows, root.cursorIndex, delta)
    if (index >= 0) root.cursorId = root.rows[index].id
  }

  function setExpanded(key, open) {
    var next = Object.assign({}, root.expanded)
    if (open) next[key] = true
    else delete next[key]
    root.expanded = next
  }

  function activate(row) {
    if (!row) return
    if (row.type === "toggle") root.systemOpen = !root.systemOpen
    else if (row.type === "group") root.setExpanded(row.group.key, !row.expanded)
  }

  function openOrClose(row, open) {
    if (!row) return
    if (row.type === "toggle") root.systemOpen = open
    else if (row.type === "group") root.setExpanded(row.group.key, open)
    else if (row.type === "process" && !open) {
      root.setExpanded(row.group.key, false)
      root.cursorId = "g:" + row.group.key
    }
  }

  function askTerminate(row) {
    if (!Model.canTerminate(row)) return
    root.cursorId = row.id
    root.confirmForce = Model.pendingState(root.pending, row.id, Date.now()) === "stuck"
    root.confirmRow = row
    confirm.selectedIndex = 0   // Enter defaults to Cancel
    keyCatcher.forceActiveFocus()
  }

  function cancelTerminate() {
    root.confirmRow = null
  }

  function confirmTerminate() {
    var row = root.confirmRow
    root.confirmRow = null
    if (!row) return
    if (helper.run(Model.commandFor(row, root.confirmForce)))
      root.pending = Model.markPending(root.pending, row.id, Date.now())
  }

  function applySnapshot(next) {
    // Rebuilding the model resets the view; put the scroll position back.
    var y = list.contentY
    root.snapshot = next
    root.pending = Model.prunePending(root.pending, next)
    root.errorText = ""
    Qt.callLater(function () { list.contentY = Math.max(0, Math.min(y, list.contentHeight - list.height)) })
  }

  Helper {
    id: helper
    onSnapshotReady: function (s) { root.applySnapshot(s) }
    onFailed: function (message) { root.errorText = message }
    onActionFinished: refresh()
  }

  Timer {
    interval: Math.max(1, root.setting("refreshSeconds", 2)) * 1000
    running: root.opened
    repeat: true
    onTriggered: {
      root.now = Date.now()
      helper.refresh()
    }
  }

  // Ticks root.now on its own so a pending termination escalates to "Not
  // responding" ~PENDING_GRACE_MS after being marked, independent of the
  // (much slower) refresh interval above.
  Timer {
    interval: 250
    repeat: true
    running: root.opened && Object.keys(root.pending).length > 0
    onTriggered: root.now = Date.now()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰍛"
    tooltipText: "Processes"
    onPressed: function (b) { root.toggle() }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: search
    contentWidth: popup.fittedContentWidth(Style.space(root.setting("panelWidth", 460)))
    contentHeight: popup.fittedContentHeight(Math.max(column.implicitHeight, root.confirmRow !== null ? Style.space(200) : 0))

    Item {
      id: keyRoot
      anchors.fill: parent

      // The catcher is blocked while confirming; its unhandled keys bubble here.
      Keys.onPressed: function (event) {
        if (confirm.handleKey(event)) event.accepted = true
      }

      PanelKeyCatcher {
        id: keyCatcher
        anchors.fill: parent
        blocked: search.activeFocus || root.confirmRow !== null
        onMoveRequested: function (dx, dy) {
          if (dy !== 0) root.moveCursor(dy)
          else root.openOrClose(root.cursorRow, dx > 0)
        }
        onActivateRequested: root.activate(root.cursorRow)
        onDeleteRequested: root.askTerminate(root.cursorRow)
        onCloseRequested: root.close()
        onTextKey: function (t) { if (t === "/") search.forceActiveFocus() }

        Column {
          id: column
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          spacing: Style.space(10)

          // qs.Ui TextField (Controls is namespaced as QQC so the name is not ambiguous).
          TextField {
            id: search
            width: parent.width
            placeholderText: "Search programs, processes or PIDs"
            foreground: root.bar.foreground
            Keys.onPressed: function (event) {
              if (event.key === Qt.Key_Escape) {
                if (search.text !== "") search.text = ""
                else keyCatcher.forceActiveFocus()
                event.accepted = true
              } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                keyCatcher.forceActiveFocus()
                if (root.cursorIndex < 0) root.moveCursor(1)
                event.accepted = true
              }
            }
          }

          ListView {
            id: list
            width: parent.width
            height: Math.min(contentHeight, Style.space(520))
            spacing: Style.space(4)
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height
            QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }
            model: root.rows
            currentIndex: root.cursorIndex
            onCurrentIndexChanged: if (currentIndex >= 0) Qt.callLater(function () { list.positionViewAtIndex(list.currentIndex, ListView.Contain) })

            delegate: Item {
              id: slot
              required property var modelData
              width: ListView.view.width
              height: loader.item ? loader.item.implicitHeight : 0

              readonly property bool selected: slot.modelData.id === root.cursorId
              readonly property string status: Model.pendingState(root.pending, slot.modelData.id, root.now)

              Component {
                id: sectionRow
                PanelSectionHeader {
                  text: slot.modelData.title
                  foreground: root.bar.foreground
                  fontFamily: root.bar.fontFamily
                }
              }
              Component {
                id: groupRow
                GroupRow {
                  entry: slot.modelData
                  bar: root.bar
                  selected: slot.selected
                  status: slot.status
                  onPointed: root.cursorId = slot.modelData.id
                  onActivated: root.activate(slot.modelData)
                  onTerminateRequested: root.askTerminate(slot.modelData)
                }
              }
              Component {
                id: processRow
                ProcessRow {
                  entry: slot.modelData
                  bar: root.bar
                  selected: slot.selected
                  status: slot.status
                  onPointed: root.cursorId = slot.modelData.id
                  onTerminateRequested: root.askTerminate(slot.modelData)
                }
              }
              Component {
                id: toggleRow
                ToggleRow {
                  entry: slot.modelData
                  bar: root.bar
                  selected: slot.selected
                  onPointed: root.cursorId = slot.modelData.id
                  onActivated: root.activate(slot.modelData)
                }
              }

              Loader {
                id: loader
                width: slot.width
                sourceComponent: slot.modelData.type === "section" ? sectionRow
                  : slot.modelData.type === "toggle" ? toggleRow
                  : slot.modelData.type === "group" ? groupRow
                  : processRow
              }
            }
          }

          Text {
            width: parent.width
            visible: root.rows.length === 0
            textFormat: Text.PlainText
            text: search.text !== "" ? "Nothing matches “" + search.text + "”" : "Loading…"
            color: Qt.darker(root.bar.foreground, 1.5)
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          Text {
            width: parent.width
            visible: root.errorText !== ""
            textFormat: Text.PlainText
            text: root.errorText
            color: Color.urgent
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.Wrap
          }
        }
      }

      ConfirmDialog {
        id: confirm
        anchors.fill: parent
        z: 10
        opened: root.confirmRow !== null
        message: root.confirmRow ? Model.confirmMessage(root.confirmRow, root.confirmForce) : ""
        confirmText: root.confirmForce ? "Force kill" : "Terminate"
        fontFamily: root.bar.fontFamily
        onCanceled: root.cancelTerminate()
        onConfirmed: root.confirmTerminate()
      }
    }
  }
}
