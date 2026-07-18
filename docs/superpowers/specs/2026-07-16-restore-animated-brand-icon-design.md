# Restore Animated Brand Icon Design

## Goal

Restore the historical animated InsightCut brand icon in the current React navigation without changing the brand text, navigation layout, routes, or any other animation.

## Scope

- Replace only the static clapperboard inside `BrandNavigation`.
- Preserve the current 36 x 36 pixel icon footprint and the existing `InsightCut / AI 视频工作台` copy.
- Reuse the historical visual language: rotating conic-gradient glow, quarter-turn reticle motion with pauses, and a pulsing center dot.
- Respect `prefers-reduced-motion` by disabling the icon animations.

## Implementation

`BrandNavigation.jsx` will render the icon from simple decorative spans instead of the Lucide clapperboard. The existing `.brand-mark` container remains the layout boundary.

`app.css` will restore the historical layers and keyframes, adapted to the current 36 pixel container:

- a rotating conic-gradient glow layer;
- an inset neutral panel that turns the glow into a thin border;
- four reticle corners that rotate in 90 degree steps and pause between turns;
- a small blue center dot with a pulse animation.

All new icon elements are decorative and remain hidden from assistive technology through the existing `aria-hidden` container.

## Verification

- Run the frontend test suite and production build.
- Confirm the navigation markup still exposes the same home link and brand copy.
- Confirm reduced-motion CSS disables all restored icon animations.
- Perform a local browser check at the current frontend port if the services are available.

## Non-goals

- No changes to the favicon.
- No changes to typography, spacing, header height, navigation items, or responsive behavior.
- No refactoring outside the brand icon.
