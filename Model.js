.pragma library

// Pure view logic for the OmaProcess panel. No QML types, so node can test it.

var PENDING_GRACE_MS = 3000

// Every function that writes text takes l10n, the panel's language:
//   t(key)            a string of the catalog in i18n/
//   tn(key, count)    its plural form for count
//   number(value, n)  value with n decimals, in the language's digits and separator

// Puts args into a string's %1, %2... placeholders.
function fill(template, args) {
  return String(template).replace(/%(\d)/g, function (whole, n) {
    var value = args[Number(n) - 1]
    return value === undefined ? whole : String(value)
  })
}

function formatBytes(bytes, l10n) {
  var units = ["B", "KB", "MB", "GB", "TB"]
  var value = Number(bytes) || 0
  var unit = 0
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++ }
  return l10n.number(value, unit >= 3 ? 1 : 0) + " " + units[unit]
}

function formatCpu(cpu, l10n) {
  var value = Number(cpu) || 0
  var whole = value >= 10 || Math.round(value * 10) % 10 === 0
  return l10n.number(value, whole ? 0 : 1) + "% CPU"
}

function _countedProcesses(count, l10n) {
  return fill(l10n.tn("processes", count), [l10n.number(count, 0)])
}

function groupCaption(group, l10n) {
  return _countedProcesses(group.count, l10n) + " · " + formatBytes(group.rss, l10n) + " · " + formatCpu(group.cpu, l10n)
}

function processCaption(proc, l10n) {
  return "PID " + proc.pid + " · " + formatBytes(proc.rss, l10n) + " · " + formatCpu(proc.cpu, l10n) + " · " + proc.cmd
}

// The heaviest first, by memory or by CPU. Memory settles a tie, so idle rows keep their place.
function _sorted(items, sort) {
  var field = sort === "cpu" ? "cpu" : "rss"
  return items.slice().sort(function (a, b) { return (b[field] - a[field]) || (b.rss - a.rss) })
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

function _groupRows(groups, query, expanded, system, sort) {
  var rows = []
  _sorted(groups, sort).forEach(function (group) {
    var visible = _visible(group, query)
    if (!visible) return
    var open = visible.forced || expanded[group.key] === true
    rows.push({ type: "group", id: "g:" + group.key, group: group, expanded: open, system: system })
    if (!open) return
    _sorted(visible.procs, sort).forEach(function (proc) { rows.push({ type: "process", id: "p:" + proc.pid, proc: proc, group: group }) })
  })
  return rows
}

function buildRows(snapshot, view) {
  var query = String(view.query || "").trim().toLowerCase()
  var expanded = view.expanded || {}
  var apps = _groupRows(snapshot.apps || [], query, expanded, false, view.sort)
  var system = _groupRows(snapshot.system || [], query, expanded, true, view.sort)
  var rows = []
  if (apps.length > 0) rows = rows.concat([{ type: "section", id: "section:apps" }], apps)
  if (system.length === 0) return rows
  var open = view.systemOpen === true || query !== ""
  var count = system.filter(function (r) { return r.type === "group" }).length
  rows.push({ type: "toggle", id: "system", count: count, open: open })
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

function unmarkPending(pending, id) {
  if (!Object.prototype.hasOwnProperty.call(pending, id)) return pending
  var next = Object.assign({}, pending)
  delete next[id]
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

function confirmMessage(row, force, l10n) {
  var action = force ? "confirm.kill" : "confirm.terminate"
  if (row.type === "process") return fill(l10n.t(action + ".process"), [row.proc.comm, row.proc.pid])
  var text = fill(l10n.t(action + ".program"), [row.group.name, _countedProcesses(row.group.count, l10n)])
  return row.system === true ? text + " " + l10n.t("confirm.service") : text
}

// A program can span several units; the helper ends them all, or none.
function commandFor(row, force) {
  if (row.type === "process") return [force ? "kill" : "term", String(row.proc.pid)]
  return [force ? "kill-unit" : "stop"].concat(row.group.keys || [row.group.key])
}
