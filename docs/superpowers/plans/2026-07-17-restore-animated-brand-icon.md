# Restore Animated Brand Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static clapperboard with the historical animated InsightCut focus-frame icon while preserving the current navigation layout and brand copy.

**Architecture:** Keep `BrandNavigation` as the sole markup owner and `app.css` as the sole style owner. Recreate the historical icon with decorative span layers, scoped `brand-*` class names, CSS keyframes, and a reduced-motion fallback.

**Tech Stack:** React 19, CSS, Node.js built-in test runner, Vite 4

## Global Constraints

- Change only the brand icon; preserve the current 36 x 36 pixel footprint.
- Preserve `InsightCut / AI 视频工作台`, header layout, routes, navigation items, favicon, and responsive behavior.
- Restore the rotating conic-gradient glow, quarter-turn reticle motion with pauses, and pulsing center dot.
- Disable all restored icon animations under `prefers-reduced-motion: reduce`.
- Do not include unrelated existing worktree changes in the implementation commit.

---

## File Structure

- Create `ai-kepu-video-web/frontend/tests/brandNavigation.test.mjs`: source-contract tests for the icon layers, animation timing, and accessibility fallback.
- Modify `ai-kepu-video-web/frontend/src/components/BrandNavigation.jsx`: replace the Lucide clapperboard with decorative animated-icon layers.
- Modify `ai-kepu-video-web/frontend/src/styles/app.css`: style and animate the restored icon without changing its layout footprint.

### Task 1: Restore and verify the animated brand icon

**Files:**
- Create: `ai-kepu-video-web/frontend/tests/brandNavigation.test.mjs`
- Modify: `ai-kepu-video-web/frontend/src/components/BrandNavigation.jsx:1-19`
- Modify: `ai-kepu-video-web/frontend/src/styles/app.css:24-28,78-80`
- Test: `ai-kepu-video-web/frontend/tests/brandNavigation.test.mjs`

**Interfaces:**
- Consumes: the existing `.brand-mark` layout boundary and `NavLink` home link.
- Produces: decorative `.brand-glow`, `.brand-inner`, `.brand-reticles`, `.brand-reticle-row`, `.brand-reticle-corner`, and `.brand-dot` layers inside the existing `aria-hidden="true"` container.

- [ ] **Step 1: Write the failing source-contract tests**

```js
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const component = readFileSync(new URL('../src/components/BrandNavigation.jsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/styles/app.css', import.meta.url), 'utf8')

test('brand navigation renders the historical animated icon layers', () => {
  assert.doesNotMatch(component, /\bClapperboard\b/)
  for (const className of ['brand-glow', 'brand-inner', 'brand-reticles', 'brand-reticle-row', 'brand-reticle-corner', 'brand-dot']) {
    assert.match(component, new RegExp(`className="[^"]*${className}`))
  }
  assert.match(component, /className="brand-mark" aria-hidden="true"/)
})

test('brand icon restores stepped pauses and reduced-motion behavior', () => {
  assert.match(css, /\.brand-glow\s*\{[^}]*conic-gradient[^}]*animation:\s*brand-glow-spin 4s linear infinite/s)
  assert.match(css, /@keyframes brand-reticle-snap\s*\{\s*0%, 20%\s*\{[^}]*rotate\(0deg\)[^}]*\}\s*25%, 45%\s*\{[^}]*rotate\(90deg\)/s)
  assert.match(css, /\.brand-dot\s*\{[^}]*animation:\s*brand-dot-pulse 2\.5s linear infinite/s)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.brand-glow,[\s\S]*\.brand-dot\s*\{\s*animation:\s*none/s)
})
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `cd ai-kepu-video-web/frontend && node --test tests/brandNavigation.test.mjs`

Expected: FAIL because `BrandNavigation.jsx` still imports `Clapperboard` and does not contain the historical icon layers.

- [ ] **Step 3: Replace the clapperboard with decorative icon layers**

Change the component import and brand mark to:

```jsx
import { FileText, FolderKanban, Settings } from 'lucide-react'
import { NavLink } from 'react-router'

// Keep navigationItems unchanged.

<span className="brand-mark" aria-hidden="true">
  <span className="brand-glow" />
  <span className="brand-inner" />
  <span className="brand-reticles">
    <span className="brand-reticle-row">
      <span className="brand-reticle-corner brand-reticle-tl" />
      <span className="brand-reticle-corner brand-reticle-tr" />
    </span>
    <span className="brand-reticle-row">
      <span className="brand-reticle-corner brand-reticle-bl" />
      <span className="brand-reticle-corner brand-reticle-br" />
    </span>
  </span>
  <span className="brand-dot" />
</span>
```

- [ ] **Step 4: Restore the historical styles and animations**

Replace the one-line `.brand-mark` rule and add the icon rules:

```css
.brand-mark { position: relative; isolation: isolate; width: 36px; height: 36px; flex: 0 0 auto; overflow: hidden; border-radius: 8px; background: #f5f7fa; transition: box-shadow .4s; }
.brand-mark:hover { box-shadow: 0 0 16px rgba(23, 105, 209, .5); }
.brand-glow { position: absolute; inset: 0; background: conic-gradient(from 0deg, transparent 0 60deg, #60a5fa 120deg, transparent 120deg 180deg, #1769d1 240deg, transparent 240deg 300deg, #818cf8 360deg); animation: brand-glow-spin 4s linear infinite; }
.brand-inner { position: absolute; inset: 1.5px; z-index: 1; border-radius: 6px; background: #f5f7fa; }
.brand-reticles { position: absolute; inset: 7px; z-index: 2; display: flex; flex-direction: column; justify-content: space-between; animation: brand-reticle-snap 5s cubic-bezier(.34, 1.56, .64, 1) infinite; }
.brand-reticle-row { display: flex; justify-content: space-between; }
.brand-reticle-corner { width: 7px; height: 7px; }
.brand-reticle-tl { border-top: 1.5px solid #18212f; border-left: 1.5px solid #18212f; border-radius: 1px 0 0; }
.brand-reticle-tr { border-top: 1.5px solid #18212f; border-right: 1.5px solid #18212f; border-radius: 0 1px 0 0; }
.brand-reticle-bl { border-bottom: 1.5px solid #18212f; border-left: 1.5px solid #18212f; border-radius: 0 0 0 1px; }
.brand-reticle-br { border-right: 1.5px solid #18212f; border-bottom: 1.5px solid #18212f; border-radius: 0 0 1px; }
.brand-dot { position: absolute; top: 50%; left: 50%; z-index: 2; width: 3px; height: 3px; border-radius: 50%; background: #1769d1; box-shadow: 0 0 6px rgba(23, 105, 209, .9); animation: brand-dot-pulse 2.5s linear infinite; }
```

Add the keyframes and reduced-motion fallback after the existing `spin` keyframe:

```css
@keyframes brand-glow-spin { to { transform: rotate(360deg); } }
@keyframes brand-reticle-snap {
  0%, 20% { transform: rotate(0deg); }
  25%, 45% { transform: rotate(90deg); }
  50%, 70% { transform: rotate(180deg); }
  75%, 95% { transform: rotate(270deg); }
  100% { transform: rotate(360deg); }
}
@keyframes brand-dot-pulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-50%, -50%) scale(1.4); }
}

@media (prefers-reduced-motion: reduce) {
  .brand-glow,
  .brand-reticles,
  .brand-dot { animation: none; }
  .brand-dot { transform: translate(-50%, -50%); }
}
```

- [ ] **Step 5: Run focused and full frontend verification**

Run:

```bash
cd ai-kepu-video-web/frontend
node --test tests/brandNavigation.test.mjs
npm test
npm run build
```

Expected: the focused test passes, all frontend tests pass, and Vite completes a production build without import or CSS errors.

- [ ] **Step 6: Review the bounded diff and commit only the icon restoration**

Run:

```bash
git diff --check -- ai-kepu-video-web/frontend/src/components/BrandNavigation.jsx ai-kepu-video-web/frontend/src/styles/app.css ai-kepu-video-web/frontend/tests/brandNavigation.test.mjs
git diff -- ai-kepu-video-web/frontend/src/components/BrandNavigation.jsx ai-kepu-video-web/frontend/src/styles/app.css ai-kepu-video-web/frontend/tests/brandNavigation.test.mjs
git add ai-kepu-video-web/frontend/src/components/BrandNavigation.jsx ai-kepu-video-web/frontend/src/styles/app.css ai-kepu-video-web/frontend/tests/brandNavigation.test.mjs
git commit -m "fix: restore animated brand icon"
```

Expected: the diff contains only the icon markup, icon CSS, and focused test; the commit succeeds without including the user's unrelated worktree changes.
