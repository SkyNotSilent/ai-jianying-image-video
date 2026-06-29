<template>
  <span class="brand-mark" aria-hidden="true">
    <svg viewBox="0 0 64 64" fill="none" role="img">
      <defs>
        <linearGradient id="brandSweep" x1="10" y1="8" x2="54" y2="56" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#f472b6" />
          <stop offset="0.48" stop-color="#2563eb" />
          <stop offset="1" stop-color="#818cf8" />
        </linearGradient>
        <filter id="softGlow" x="-24" y="-24" width="112" height="112" color-interpolation-filters="sRGB">
          <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#2563eb" flood-opacity="0.35" />
        </filter>
      </defs>
      <rect width="64" height="64" rx="16" fill="#f7f8fa" />
      <rect x="3" y="3" width="58" height="58" rx="13" stroke="url(#brandSweep)" stroke-width="4" filter="url(#softGlow)" />
      <rect x="7" y="7" width="50" height="50" rx="10" fill="#ffffff" />
      <g class="brand-corners">
        <path d="M18 25v-7h7" stroke="#1d2129" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M39 18h7v7" stroke="#1d2129" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M46 39v7h-7" stroke="#1d2129" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M25 46h-7v-7" stroke="#1d2129" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
      </g>
      <circle class="brand-core" cx="32" cy="32" r="3.5" fill="#2563eb" filter="url(#softGlow)" />
    </svg>
  </span>
</template>

<style scoped>
.brand-mark {
  width: 36px;
  height: 36px;
  display: inline-flex;
  flex: 0 0 auto;
  filter: drop-shadow(0 10px 20px rgba(37, 99, 235, 0.14));
}

.brand-mark svg {
  width: 100%;
  height: 100%;
  display: block;
}

.brand-corners {
  transform-origin: 32px 32px;
  animation: brand-spin 5s linear infinite;
}

.brand-core {
  animation: brand-pulse 2.5s ease-in-out infinite;
}

@keyframes brand-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes brand-pulse {
  0%,
  100% {
    r: 3.5;
  }
  50% {
    r: 4.8;
  }
}

@media (prefers-reduced-motion: reduce) {
  .brand-corners,
  .brand-core {
    animation: none;
  }
}
</style>
