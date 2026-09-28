import QtQuick
import qs.Commons
import qs.Ui

// "SYSTEM (12)" header that opens and closes the session-services section.
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
  implicitHeight: label.implicitHeight + Style.spacing.rowPaddingX

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onContainsMouseChanged: if (containsMouse) row.pointed()
    onClicked: row.activated()
  }

  PanelSectionHeader {
    id: label
    anchors.left: parent.left
    anchors.leftMargin: Style.space(10)
    anchors.verticalCenter: parent.verticalCenter
    text: (row.entry.open ? "󰅀 " : "󰅂 ") + row.entry.title + " (" + row.entry.count + ")"
    foreground: row.bar.foreground
    fontFamily: row.bar.fontFamily
  }
}
