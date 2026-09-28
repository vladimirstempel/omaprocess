// Run with: node --test tests/model.test.js
const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")

const source = fs.readFileSync(path.join(__dirname, "..", "Model.js"), "utf8").replace(/^\.pragma library\s*$/m, "")
const M = {}
vm.createContext(M)
vm.runInContext(source, M)

const proc = (pid, comm, extra = {}) => ({ pid, comm, cmd: comm, rss: 1024, cpu: 0, protected: false, ...extra })
const group = (key, name, procs, extra = {}) => ({
  key, unit: key, name, icon: "", count: procs.length, rss: 2048, cpu: 1.5, protected: false, procs, ...extra,
})
const SNAPSHOT = {
  apps: [
    group("app-c.scope", "Chromium", [proc(10, "chromium"), proc(11, "chromium")]),
    group("app-z.scope", "Zed", [proc(20, "zed-editor"), proc(21, "bash")]),
  ],
  system: [group("pipewire.service", "Pipewire", [proc(30, "pipewire")])],
}
const view = (extra = {}) => ({ query: "", expanded: {}, systemOpen: false, ...extra })
const ids = rows => rows.map(r => r.id)
const plainValue = v => JSON.parse(JSON.stringify(v))

test("formats sizes and cpu", () => {
  assert.equal(M.formatBytes(12 * 1024), "12 KB")
  assert.equal(M.formatBytes(340 * 1024 * 1024), "340 MB")
  assert.equal(M.formatBytes(1.24 * 1024 ** 3), "1.2 GB")
  assert.equal(M.formatCpu(0), "0% CPU")
  assert.equal(M.formatCpu(3.14), "3.1% CPU")
  assert.equal(M.formatCpu(45.6), "46% CPU")
})

test("captions", () => {
  assert.equal(M.groupCaption(SNAPSHOT.apps[0]), "2 processes · 2 KB · 1.5% CPU")
  assert.equal(M.groupCaption(group("k", "n", [proc(1, "x")])), "1 process · 2 KB · 1.5% CPU")
  assert.equal(M.processCaption(proc(10, "chromium", { cmd: "/usr/bin/chromium --x" })), "PID 10 · 1 KB · 0% CPU · /usr/bin/chromium --x")
})

test("collapsed view lists apps and a closed system toggle", () => {
  const rows = M.buildRows(SNAPSHOT, view())
  assert.deepEqual(plainValue(ids(rows)), ["section:apps", "g:app-c.scope", "g:app-z.scope", "system"])
  assert.equal(rows[3].count, 1)
  assert.equal(rows[3].open, false)
})

test("expanded group and open system section", () => {
  const rows = M.buildRows(SNAPSHOT, view({ expanded: { "app-z.scope": true }, systemOpen: true }))
  assert.deepEqual(plainValue(ids(rows)), ["section:apps", "g:app-c.scope", "g:app-z.scope", "p:20", "p:21", "system", "g:pipewire.service"])
})

test("query matches group names, process names and pids", () => {
  assert.deepEqual(plainValue(ids(M.buildRows(SNAPSHOT, view({ query: "chro" })))), ["section:apps", "g:app-c.scope"])
  // matched through a process only: shown expanded with just the matching processes
  assert.deepEqual(plainValue(ids(M.buildRows(SNAPSHOT, view({ query: "bash" })))), ["section:apps", "g:app-z.scope", "p:21"])
  assert.deepEqual(plainValue(ids(M.buildRows(SNAPSHOT, view({ query: "20" })))), ["section:apps", "g:app-z.scope", "p:20"])
  // a query opens the system section when it matches there
  assert.deepEqual(plainValue(ids(M.buildRows(SNAPSHOT, view({ query: "pipe" })))), ["system", "g:pipewire.service"])
  assert.deepEqual(plainValue(M.buildRows(SNAPSHOT, view({ query: "nothing" }))), [])
})

test("cursor survives a rebuild by id, and skips section headers", () => {
  const before = M.buildRows(SNAPSHOT, view())
  const reordered = { apps: [SNAPSHOT.apps[1], SNAPSHOT.apps[0]], system: SNAPSHOT.system }
  const after = M.buildRows(reordered, view())
  assert.equal(M.indexOfId(after, before[1].id), 2)
  assert.equal(M.indexOfId(after, "g:gone"), -1)
  assert.equal(M.stepCursor(after, -1, 1), 1)
  assert.equal(M.stepCursor(after, 1, -1), 1)
  assert.equal(M.stepCursor(after, 1, 1), 2)
  assert.equal(M.stepCursor(after, 3, 1), 3)
  assert.equal(M.stepCursor([], -1, 1), -1)
})

test("pending becomes stuck after the grace period and is pruned when gone", () => {
  let pending = M.markPending({}, "g:app-c.scope", 1000)
  assert.equal(M.pendingState(pending, "g:app-c.scope", 1000 + 2999), "terminating")
  assert.equal(M.pendingState(pending, "g:app-c.scope", 1000 + 3000), "stuck")
  assert.equal(M.pendingState(pending, "p:1", 1000), "")
  pending = M.markPending(pending, "p:99", 1000)
  assert.deepEqual(Object.keys(M.prunePending(pending, SNAPSHOT)), ["g:app-c.scope"])
})

test("terminate commands, messages and protection", () => {
  const rows = M.buildRows(SNAPSHOT, view({ expanded: { "app-c.scope": true }, systemOpen: true }))
  const chromium = rows[1], renderer = rows[2], pipewire = rows[rows.length - 1]
  assert.deepEqual(plainValue(M.commandFor(chromium, false)), ["stop", "app-c.scope"])
  assert.deepEqual(plainValue(M.commandFor(chromium, true)), ["kill-unit", "app-c.scope"])
  assert.deepEqual(plainValue(M.commandFor(renderer, false)), ["term", "10"])
  assert.deepEqual(plainValue(M.commandFor(renderer, true)), ["kill", "10"])
  assert.equal(M.confirmMessage(chromium, false), "Terminate Chromium? (2 processes)")
  assert.equal(M.confirmMessage(renderer, true), "Force kill chromium (PID 10)? It will not get a chance to save.")
  assert.match(M.confirmMessage(pipewire, false), /session service/)
  assert.equal(M.canTerminate(chromium), true)
  assert.equal(M.canTerminate({ type: "group", group: group("k", "Shell", [], { protected: true }) }), false)
  assert.equal(M.canTerminate({ type: "process", proc: proc(1, "qs", { protected: true }) }), false)
  assert.equal(M.canTerminate(rows[0]), false)
})
