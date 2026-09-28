import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "../Model.js" as Model

// One program: icon, name, "47 processes · 1.2 GB · 3% CPU", terminate button.
CursorSurface {
  id: row

  required property var entry
  required property QtObject bar
  property bool selected: false
  property string status: ""      // "", "terminating", "stuck"

  signal activated()
  signal terminateRequested()
  signal pointed()

  readonly property var group: row.entry.group
  readonly property string iconSource: {
    var icon = String(group.icon || "")
    if (icon === "") return ""
    if (icon.charAt(0) === "/") return "file://" + icon
    return Quickshell.iconPath(icon, true)
  }

  hasCursor: selected
  foreground: bar.foreground
  implicitHeight: content.implicitHeight + Style.spacing.rowPaddingX

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onContainsMouseChanged: if (containsMouse) row.pointed()
    onClicked: row.activated()
  }

  Item {
    id: content
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: Style.space(10)
    anchors.rightMargin: Style.space(10)
    implicitHeight: Math.max(icon.height, labels.implicitHeight, endButton.implicitHeight)

    Image {
      id: icon
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(22)
      height: Style.space(22)
      visible: row.iconSource !== ""
      source: row.iconSource
      fillMode: Image.PreserveAspectFit
      sourceSize.width: width * Screen.devicePixelRatio
      sourceSize.height: height * Screen.devicePixelRatio
    }

    Text {
      anchors.centerIn: icon
      visible: row.iconSource === ""
      textFormat: Text.PlainText
      text: row.entry.expanded ? "󰅀" : "󰅂"
      color: row.bar.foreground
      font.family: row.bar.fontFamily
      font.pixelSize: Style.font.heading
    }

    Column {
      id: labels
      anchors.left: icon.right
      anchors.leftMargin: Style.space(10)
      anchors.right: endButton.left
      anchors.rightMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(1)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: row.group.name
        color: row.bar.foreground
        font.family: row.bar.fontFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: row.status === "terminating" ? "Terminating…"
            : row.status === "stuck" ? "Not responding"
            : Model.groupCaption(row.group)
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
