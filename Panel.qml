pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model
import "components"

// Bar button plus popup. The panel owns the state (query, sort, expanded
// groups, cursor, pending terminations) and delegates I/O to Helper and every
// decision about rows to Model.js. The popup's content is built when the panel
// first opens, so the functions that touch its items live inside it.
Panel {
  id: root
  moduleName: "omaprocess"
  // No ipcTarget: the bar builds one widget per monitor and only the first
  // could own the target, so the panel opened on the wrong screen. The shell
  // reaches the widget on the focused monitor: omarchy-shell shell toggle omaprocess

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ apps: [], system: [] })
  property string query: ""
  // The setting is where it starts; the panel can change it until the shell restarts.
  property string sort: String(root.setting("sortBy", "Memory")).toLowerCase() === "cpu" ? "cpu" : "memory"
  property var expanded: ({})
  property bool systemOpen: false
  property string cursorId: ""
  property var pending: ({})
  property real now: Date.now()
  property string errorText: ""
  property string actionError: ""
  property string pendingActionId: ""
  property var confirmRow: null
  property bool confirmForce: false

  readonly property var rows: Model.buildRows(root.snapshot, { query: root.query, sort: root.sort, expanded: root.expanded, systemOpen: root.systemOpen })
  readonly property Item view: popup.loadedContent

  Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  // What Model.js needs to write text. A new object on every language change,
  // so the bindings that pass it on are evaluated again.
  readonly property var l10n: {
    var catalog = strings.strings
    var decimal = I18n.decimal
    return {
      t: function (key) { return strings.t(key) },
      tn: function (key, count) { return strings.tn(key, count) },
      number: function (value, decimals) { return I18n.formatNumber(value, decimals) }
    }
  }
  readonly property int cursorIndex: Model.indexOfId(root.rows, root.cursorId)
  readonly property var cursorRow: root.cursorIndex >= 0 ? root.rows[root.cursorIndex] : null

  onOpenedChanged: {
    root.confirmRow = null
    if (!opened) return
    root.query = ""
    root.errorText = ""
    root.actionError = ""
    root.cursorId = ""
    helper.refresh()
  }

  function moveCursor(delta) {
    var index = Model.stepCursor(root.rows, root.cursorIndex, delta)
    if (index >= 0) root.cursorId = root.rows[index].id
    root.scrollToCursor()
  }

  function scrollToCursor() {
    if (root.view) root.view.scrollToCursor()
  }

  function toggleSort() {
    root.sort = root.sort === "cpu" ? "memory" : "cpu"
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
      root.scrollToCursor()
    }
  }

  function askTerminate(row) {
    if (!Model.canTerminate(row)) return
    root.cursorId = row.id
    root.confirmForce = Model.pendingState(root.pending, row.id, Date.now()) === "stuck"
    root.confirmRow = row
    if (root.view) root.view.beginConfirm()
  }

  function cancelTerminate() {
    root.confirmRow = null
  }

  function confirmTerminate() {
    var row = root.confirmRow
    root.confirmRow = null
    if (!row) return
    root.actionError = ""
    if (helper.run(Model.commandFor(row, root.confirmForce))) {
      root.pendingActionId = row.id
      root.pending = Model.markPending(root.pending, row.id, Date.now())
    } else {
      root.actionError = root.l10n.t("error.busy")
    }
  }

  function applySnapshot(next) {
    root.snapshot = next
    root.pending = Model.prunePending(root.pending, next)
    root.errorText = ""
    if (root.view) root.view.clampScroll()
  }

  Helper {
    id: helper
    onSnapshotReady: function (s) { root.applySnapshot(s) }
    onFailed: function (message) {
      root.errorText = message
      // pendingActionId is still set here: actionFinished(ok) clears it right
      // after this, so its presence marks this failure as the action's, not
      // an unrelated list-refresh failure (which must not populate actionError).
      if (root.pendingActionId !== "") root.actionError = message
    }
    onActionFinished: function (ok) {
      if (!ok && root.pendingActionId !== "")
        root.pending = Model.unmarkPending(root.pending, root.pendingActionId)
      root.pendingActionId = ""
      refresh()
    }
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
    tooltipText: root.l10n.t("tooltip")
    onPressed: function (b) { root.toggle() }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: root.view ? root.view.searchField : null
    contentWidth: popup.fittedContentWidth(Style.space(root.setting("panelWidth", 460)))
    contentHeight: popup.fittedContentHeight(Math.max(popup.loadedContentHeight, root.confirmRow !== null ? Style.space(200) : 0))

    content: Item {
      id: body
      anchors.fill: parent
      implicitHeight: column.implicitHeight

      readonly property Item searchField: search

      // Keyboard moves bring the cursor into view; refreshes and hover never scroll.
      function scrollToCursor() {
        Qt.callLater(function () {
          var item = rowRepeater.itemAt(root.cursorIndex)
          if (!item) return
          if (item.y < list.contentY) list.contentY = item.y
          else if (item.y + item.height > list.contentY + list.height) list.contentY = item.y + item.height - list.height
        })
      }

      // Rows can vanish under the view; pull it back only if it now ends past the content.
      function clampScroll() {
        Qt.callLater(function () { list.contentY = Math.max(0, Math.min(list.contentY, list.contentHeight - list.height)) })
      }

      function beginConfirm() {
        confirm.selectedIndex = 0   // Enter defaults to Cancel
        keyCatcher.forceActiveFocus()
      }

      // The content outlives a close: start the next open with an empty search.
      Connections {
        target: root
        function onOpenedChanged() { if (root.opened) search.text = "" }
      }
      Component.onCompleted: Qt.callLater(function () { search.forceActiveFocus() })

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
        onTextKey: function (t) {
          if (t === "/") search.forceActiveFocus()
          else if (t === "s" || t === "S") root.toggleSort()
        }

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
            placeholderText: root.l10n.t("search.placeholder")
            foreground: root.bar.foreground
            onTextChanged: root.query = text
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

          Item {
            width: parent.width
            implicitHeight: sortChoice.implicitHeight

            ButtonGroup {
              id: sortChoice
              anchors.right: parent.right
              options: [{ value: "memory", label: root.l10n.t("sort.memory") }, { value: "cpu", label: root.l10n.t("sort.cpu") }]
              value: root.sort
              focusable: false
              foreground: root.bar.foreground
              fontFamily: root.bar.fontFamily
              fontSize: Style.font.caption
              onChanged: function (value) { root.sort = value }
            }
          }

          // Flickable + Repeater, not ListView: a new rows array reset ListView's
          // position every refresh, and its estimated contentHeight made long lists jump.
          Flickable {
            id: list
            width: parent.width
            height: Math.min(contentHeight, Style.space(520))
            contentHeight: listColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height
            QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AsNeeded }

            Column {
              id: listColumn
              width: list.width
              spacing: Style.space(4)

              Repeater {
                id: rowRepeater
                // A count, not the array: same-length refreshes rebind rows in place.
                model: root.rows.length

                delegate: Item {
                  id: slot
                  required property int index
                  // rows can shrink a moment before the count does
                  readonly property var modelData: root.rows[slot.index] || ({ id: "", type: "section" })
                  width: listColumn.width
                  height: loader.item ? loader.item.implicitHeight : 0

                  readonly property bool selected: slot.modelData.id === root.cursorId
                  readonly property string status: Model.pendingState(root.pending, slot.modelData.id, root.now)

                  Component {
                    id: sectionRow
                    PanelSectionHeader {
                      text: root.l10n.t("section.apps")
                      foreground: root.bar.foreground
                      fontFamily: root.bar.fontFamily
                    }
                  }
                  Component {
                    id: groupRow
                    GroupRow {
                      entry: slot.modelData
                      bar: root.bar
                      l10n: root.l10n
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
                      l10n: root.l10n
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
                      l10n: root.l10n
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
            }
          }

          Text {
            width: parent.width
            visible: root.rows.length === 0 && root.errorText === ""
            textFormat: Text.PlainText
            text: search.text !== "" ? Model.fill(root.l10n.t("empty.nothing"), [search.text]) : root.l10n.t("empty.loading")
            color: Qt.darker(root.bar.foreground, 1.5)
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          Text {
            width: parent.width
            visible: root.errorText !== "" || root.actionError !== ""
            textFormat: Text.PlainText
            text: root.errorText || root.actionError
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
        message: root.confirmRow ? Model.confirmMessage(root.confirmRow, root.confirmForce, root.l10n) : ""
        confirmText: root.l10n.t(root.confirmForce ? "action.kill" : "action.terminate")
        fontFamily: root.bar.fontFamily
        onCanceled: root.cancelTerminate()
        onConfirmed: root.confirmTerminate()
      }
    }
  }
}
