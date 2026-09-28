import QtQuick
import qs.Commons
import qs.Ui
import "../Model.js" as Model

// One process inside an expanded program, indented under it.
CursorSurface {
  id: row

  required property var entry
  required property QtObject bar
  property bool selected: false
  property string status: ""

  signal activated()
  signal terminateRequested()
  signal pointed()

  hasCursor: selected
  foreground: bar.foreground
  implicitHeight: content.implicitHeight + Style.spacing.rowPaddingX

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    onContainsMouseChanged: if (containsMouse) row.pointed()
  }

  Item {
    id: content
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: Style.space(42)
    anchors.rightMargin: Style.space(10)
    implicitHeight: Math.max(labels.implicitHeight, endButton.implicitHeight)

    Column {
      id: labels
      anchors.left: parent.left
      anchors.right: endButton.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(1)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: row.entry.proc.comm
        color: row.bar.foreground
        font.family: row.bar.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: row.status === "terminating" ? "Terminating…"
            : row.status === "stuck" ? "Not responding"
            : Model.processCaption(row.entry.proc)
        color: row.status === "stuck" ? Color.urgent : Qt.darker(row.bar.foreground, 1.4)
        font.family: row.bar.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }
    }

    PanelActionButton {
      id: endButton
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      visible: Model.canTerminate(row.entry)
      iconText: row.status === "stuck" ? "󰚌" : "󰅙"
      tooltipText: row.status === "stuck" ? "Force kill" : "Terminate"
      foreground: row.bar.foreground
      hoverColor: Color.urgent
      fontFamily: row.bar.fontFamily
      onClicked: row.terminateRequested()
    }
  }
}
