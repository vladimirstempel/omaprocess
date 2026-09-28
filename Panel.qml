pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "omaprocess"
  ipcTarget: "omaprocess"

  // The bar sizes a widget slot from the root's implicit size.
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property var snapshot: ({ apps: [], system: [] })
  property string errorText: ""

  onOpenedChanged: if (opened) helper.refresh()

  Helper {
    id: helper
    onSnapshotReady: function (s) { root.snapshot = s; root.errorText = "" }
    onFailed: function (message) { root.errorText = message }
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
    contentWidth: popup.fittedContentWidth(Style.space(root.setting("panelWidth", 460)))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    Column {
      id: column
      anchors.left: parent.left
      anchors.right: parent.right
      spacing: Style.space(10)

      Text {
        textFormat: Text.PlainText
        text: root.snapshot.apps.length + " programs"
        color: root.bar.foreground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.body
      }
    }
  }
}
