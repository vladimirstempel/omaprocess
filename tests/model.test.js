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

// The panel's language, as Commons.Translations gives it. English needs only one and other.
const catalog = code => JSON.parse(fs.readFileSync(path.join(__dirname, "..", "i18n", code + ".json"), "utf8"))
const language = (strings, plural, decimal = ".") => ({
  t: key => (typeof strings[key] === "object" ? strings[key].other : strings[key]) || key,
  tn: (key, count) => strings[key][plural(count)],
  number: (value, decimals) => Number(value).toFixed(decimals).replace(".", decimal),
})
const EN = language(catalog("en"), n => (n === 1 ? "one" : "other"))
const russianPlural = n => (n % 10 === 1 && n % 100 !== 11 ? "one"
  : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "few" : "many")
const RU = language(catalog("ru"), russianPlural, ",")

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
  assert.equal(M.formatBytes(12 * 1024, EN), "12 KB")
  assert.equal(M.formatBytes(340 * 1024 * 1024, EN), "340 MB")
  assert.equal(M.formatBytes(1.24 * 1024 ** 3, EN), "1.2 GB")
  assert.equal(M.formatCpu(0, EN), "0% CPU")
  assert.equal(M.formatCpu(3.14, EN), "3.1% CPU")
  assert.equal(M.formatCpu(45.6, EN), "46% CPU")
})

test("captions", () => {
  assert.equal(M.groupCaption(SNAPSHOT.apps[0], EN), "2 processes · 2 KB · 1.5% CPU")
  assert.equal(M.groupCaption(group("k", "n", [proc(1, "x")]), EN), "1 process · 2 KB · 1.5% CPU")
  assert.equal(M.processCaption(proc(10, "chromium", { cmd: "/usr/bin/chromium --x" }), EN), "PID 10 · 1 KB · 0% CPU · /usr/bin/chromium --x")
})

test("another language takes its own plural forms and decimal separator", () => {
  const captions = [1, 3, 5, 21].map(count => M.groupCaption({ count, rss: 1.24 * 1024 ** 3, cpu: 3.14 }, RU))
  assert.deepEqual(captions, ["1 процесс · 1,2 GB · 3,1% CPU", "3 процесса · 1,2 GB · 3,1% CPU",
    "5 процессов · 1,2 GB · 3,1% CPU", "21 процесс · 1,2 GB · 3,1% CPU"])
  const row = { type: "group", group: { name: "Zed", count: 2 }, system: true }
  assert.equal(M.confirmMessage(row, true, RU),
    "Принудительно завершить Zed? (2 процесса) Данные не будут сохранены. Это служба сеанса: рабочий стол может перестать работать.")
})

test("every language has the strings English has", () => {
  const english = Object.keys(catalog("en")).sort()
  for (const file of fs.readdirSync(path.join(__dirname, "..", "i18n")))
    assert.deepEqual(Object.keys(catalog(path.basename(file, ".json"))).sort(), english, file)
})

test("sorts programs and their processes by memory or by cpu", () => {
  const snapshot = { apps: [
    group("app-a.scope", "A", [proc(1, "a", { rss: 10, cpu: 9 }), proc(2, "a", { rss: 90, cpu: 1 })], { rss: 100, cpu: 10 }),
    group("app-b.scope", "B", [proc(3, "b")], { rss: 900, cpu: 2 }),
    group("app-c.scope", "C", [proc(4, "c")], { rss: 500, cpu: 2 }),
  ], system: [] }
  const all = { "app-a.scope": true }
  assert.deepEqual(plainValue(ids(M.buildRows(snapshot, view({ expanded: all })))),
    ["section:apps", "g:app-b.scope", "g:app-c.scope", "g:app-a.scope", "p:2", "p:1"])
  // equal cpu: the one that holds more memory comes first
  assert.deepEqual(plainValue(ids(M.buildRows(snapshot, view({ expanded: all, sort: "cpu" })))),
    ["section:apps", "g:app-a.scope", "p:1", "p:2", "g:app-b.scope", "g:app-c.scope"])
  assert.equal(snapshot.apps[0].key, "app-a.scope") // the snapshot keeps its order
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

test("unmarkPending removes one id without mutating the input and leaves others", () => {
  const pending = M.markPending(M.markPending({}, "g:a", 1000), "p:1", 1000)
  const next = M.unmarkPending(pending, "g:a")
  assert.deepEqual(Object.keys(next), ["p:1"])
  assert.deepEqual(Object.keys(pending), ["g:a", "p:1"]) // input untouched
  assert.deepEqual(M.unmarkPending(pending, "missing"), pending) // no-op, still a plain object
})

test("terminate commands, messages and protection", () => {
  const rows = M.buildRows(SNAPSHOT, view({ expanded: { "app-c.scope": true }, systemOpen: true }))
  const chromium = rows[1], renderer = rows[2], pipewire = rows[rows.length - 1]
  assert.deepEqual(plainValue(M.commandFor(chromium, false)), ["stop", "app-c.scope"])
  assert.deepEqual(plainValue(M.commandFor(chromium, true)), ["kill-unit", "app-c.scope"])
  const merged = { type: "group", group: group("app-c.scope", "Chromium", [], { keys: ["app-c.scope", "app-c-2.scope"] }) }
  assert.deepEqual(plainValue(M.commandFor(merged, false)), ["stop", "app-c.scope", "app-c-2.scope"])
  assert.deepEqual(plainValue(M.commandFor(merged, true)), ["kill-unit", "app-c.scope", "app-c-2.scope"])
  assert.deepEqual(plainValue(M.commandFor(renderer, false)), ["term", "10"])
  assert.deepEqual(plainValue(M.commandFor(renderer, true)), ["kill", "10"])
  assert.equal(M.confirmMessage(chromium, false, EN), "Terminate Chromium? (2 processes)")
  assert.equal(M.confirmMessage(renderer, true, EN), "Force kill chromium (PID 10)? It will not get a chance to save.")
  assert.match(M.confirmMessage(pipewire, false, EN), /session service/)
  assert.equal(M.canTerminate(chromium), true)
  assert.equal(M.canTerminate({ type: "group", group: group("k", "Shell", [], { protected: true }) }), false)
  assert.equal(M.canTerminate({ type: "process", proc: proc(1, "qs", { protected: true }) }), false)
  assert.equal(M.canTerminate(rows[0]), false)
})
