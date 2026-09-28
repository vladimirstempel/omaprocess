.pragma library

// Pure view logic for the OmaProcess panel. No QML types, so node can test it.

var PENDING_GRACE_MS = 3000

function formatBytes(bytes) {
  var units = ["B", "KB", "MB", "GB", "TB"]
  var value = Number(bytes) || 0
  var unit = 0
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++ }
  var digits = unit >= 3 ? 1 : 0
  return value.toFixed(digits) + " " + units[unit]
}

function formatCpu(cpu) {
  var value = Number(cpu) || 0
  var shown = value >= 10 ? Math.round(value) : Math.round(value * 10) / 10
  return shown + "% CPU"
}

function groupCaption(group) {
  var noun = group.count === 1 ? " process" : " processes"
  return group.count + noun + " · " + formatBytes(group.rss) + " · " + formatCpu(group.cpu)
}

function processCaption(proc) {
  return "PID " + proc.pid + " · " + formatBytes(proc.rss) + " · " + formatCpu(proc.cpu) + " · " + proc.cmd
}

function _contains(text, query) {
  return String(text).toLowerCase().indexOf(query) >= 0
}

// One group as it should appear for this query: null when it does not match,
// otherwise the processes to show and whether the query forces it open.
function _visible(group, query) {
  if (query === "" || _contains(group.name, query)) return { procs: group.procs, forced: false }
  var procs = group.procs.filter(function (p) { return _contains(p.comm, query) || String(p.pid) === query || _contains(p.pid, query) })
  return procs.length > 0 ? { procs: procs, forced: true } : null
}

function _groupRows(groups, query, expanded, system) {
  var rows = []
  groups.forEach(function (group) {
    var visible = _visible(group, query)
    if (!visible) return
    var open = visible.forced || expanded[group.key] === true
    rows.push({ type: "group", id: "g:" + group.key, group: group, expanded: open, system: system })
    if (!open) return
    visible.procs.forEach(function (proc) { rows.push({ type: "process", id: "p:" + proc.pid, proc: proc, group: group }) })
  })
  return rows
}

function buildRows(snapshot, view) {
  var query = String(view.query || "").trim().toLowerCase()
  var expanded = view.expanded || {}
  var apps = _groupRows(snapshot.apps || [], query, expanded, false)
  var system = _groupRows(snapshot.system || [], query, expanded, true)
  var rows = []
  if (apps.length > 0) rows = rows.concat([{ type: "section", id: "section:apps", title: "APPLICATIONS" }], apps)
  if (system.length === 0) return rows
  var open = view.systemOpen === true || query !== ""
  var count = system.filter(function (r) { return r.type === "group" }).length
  rows.push({ type: "toggle", id: "system", title: "SYSTEM", count: count, open: open })
  return open ? rows.concat(system) : rows
}

function isSelectable(row) {
  return !!row && row.type !== "section"
}

function indexOfId(rows, id) {
  for (var i = 0; i < rows.length; i++) if (rows[i].id === id) return i
  return -1
}

// Next selectable row from index in direction delta; stays put at the ends.
function stepCursor(rows, index, delta) {
  var start = index < 0 ? (delta > 0 ? -1 : rows.length) : index
  for (var i = start + delta; i >= 0 && i < rows.length; i += delta) if (isSelectable(rows[i])) return i
  return index >= 0 ? index : -1
}

function markPending(pending, id, now) {
  var next = Object.assign({}, pending)
  next[id] = now
  return next
}

function pendingState(pending, id, now) {
  if (!Object.prototype.hasOwnProperty.call(pending, id)) return ""
  return now - pending[id] >= PENDING_GRACE_MS ? "stuck" : "terminating"
}

function prunePending(pending, snapshot) {
  var alive = {}
  ;(snapshot.apps || []).concat(snapshot.system || []).forEach(function (group) {
    alive["g:" + group.key] = true
    group.procs.forEach(function (proc) { alive["p:" + proc.pid] = true })
  })
  var next = {}
  Object.keys(pending).forEach(function (id) { if (alive[id]) next[id] = pending[id] })
  return next
}

function canTerminate(row) {
  if (!row) return false
  if (row.type === "group") return !row.group.protected
  if (row.type === "process") return !row.proc.protected
  return false
}

function confirmMessage(row, force) {
  var verb = force ? "Force kill " : "Terminate "
  var tail = force ? " It will not get a chance to save." : ""
  if (row.type === "process") return verb + row.proc.comm + " (PID " + row.proc.pid + ")?" + tail
  var noun = row.group.count === 1 ? " process" : " processes"
  var text = verb + row.group.name + "? (" + row.group.count + noun + ")" + tail
  if (row.system === true) text += " This is a session service; the desktop may stop working."
  return text
}

function commandFor(row, force) {
  if (row.type === "process") return [force ? "kill" : "term", String(row.proc.pid)]
  return [force ? "kill-unit" : "stop", row.group.key]
}
