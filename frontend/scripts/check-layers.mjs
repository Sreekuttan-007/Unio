// Protects the boundary that lets the UI be restyled safely. Run with: npm run lint
//
//   src/ui        presentation only: props in, markup out. No data, routing or session.
//   src/styles    the only place raw colours and sizes may be defined.
//   everything    no raw hex colours, colour functions or arbitrary pixel sizes in components.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../src/', import.meta.url))
const failures = []

function walk(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

const files = walk(ROOT).filter((file) => /\.(tsx?|css)$/.test(file))
const isTest = (file) => /\.test\.tsx?$/.test(file) || file.includes(`${sep}test${sep}`)

const UI_FORBIDDEN = [
  [/from ['"]@\/(platform|features|mocks|app)/, 'ui/ may not import platform, features, mocks or app'],
  [/from ['"]react-router/, 'ui/ may not use the router (take an onNavigate prop instead)'],
  [/from ['"]@tanstack/, 'ui/ may not fetch data (take props instead)'],
  [/\bfetch\(/, 'ui/ may not call fetch'],
  [/\buseAuth\b|\buseQuery\b|\buseMutation\b|\bsessionStorage\b/, 'ui/ may not read the session or server state'],
]

const RAW_STYLE = [
  [/#[0-9a-fA-F]{3,8}\b/, 'raw hex colour (use a token from styles/tokens.css)'],
  [/\b(?:rgb|rgba|hsl|hsla|oklch|oklab)\(/, 'raw colour function (use a token from styles/tokens.css)'],
  [/\[\d+(?:\.\d+)?px\]/, 'arbitrary pixel size (use a token or a Tailwind scale value)'],
]

for (const file of files) {
  const name = relative(ROOT, file).split(sep).join('/')
  const text = readFileSync(file, 'utf8')
  const lines = text.split('\n')

  lines.forEach((line, index) => {
    const report = (message) => failures.push(`${name}:${index + 1}  ${message}\n    ${line.trim()}`)

    if (name.startsWith('ui/') && !isTest(file)) {
      for (const [pattern, message] of UI_FORBIDDEN) if (pattern.test(line)) report(message)
    }
    if (name === 'styles/tokens.css' || isTest(file) || name.startsWith('mocks/')) return
    const code = line.replace(/\/\/.*$/, '')
    for (const [pattern, message] of RAW_STYLE) if (pattern.test(code)) report(message)
  })

  const importsMocks = /from ['"]@\/mocks/.test(text) || /import\(['"]@\/mocks/.test(text)
  if (importsMocks && !isTest(file) && name !== 'main.tsx' && !name.startsWith('mocks/')) {
    failures.push(`${name}  only main.tsx and tests may import mocks`)
  }
}

if (failures.length > 0) {
  console.error(`Layer check failed (${failures.length}):\n`)
  console.error(failures.join('\n'))
  process.exit(1)
}
console.log(`Layer check passed (${files.length} files).`)
