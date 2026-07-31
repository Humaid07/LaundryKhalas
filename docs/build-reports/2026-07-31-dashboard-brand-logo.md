# Build Report — LaundryKhalas logo in both dashboards

- **Date:** 2026-07-31
- **Author:** Claude Code

## 1. Task objective
Add the real LaundryKhalas logo to the brand area of both dashboards
(`apps/admin` command center + `apps/facility-dashboard` partner portal),
replacing the placeholder rose-tile SVG droplet, while keeping the dynamic
facility name intact and not breaking collapsed / mobile layouts.

## 2. What was built
- Selected and prepared a clean, transparent **icon mark** from the two supplied
  source files, and wired it into the shared `BrandMark` of both apps so it
  propagates to every sidebar, header, and login screen.

## 3. Why it was built
Product branding: the dashboards previously showed a generic hand-drawn droplet
in a pink tile, not the actual LaundryKhalas mark.

## 4. Logo selection (quality check)
Two source files were supplied in `~/Downloads`:

| File | Content | Background | Verdict |
|------|---------|------------|---------|
| `laundrykhalas logo.png` (3184×1344) | icon-only mark | **solid white** (0% transparent) | would show a white box on the dark sidebar |
| `logo_laundry_khalas-removebg-preview.png` (500×211) | full wordmark + **black** Arabic sub-text | transparent | black Arabic text vanishes on dark; wordmark duplicates the UI "LaundryKhalas" label |

Neither was directly usable. Since the requested layout is **`[mark] LaundryKhalas /
SUBTITLE`** (an icon beside UI text), the icon-only file was the right base — but it
needed its white background removed. A small Pillow script keyed out the white
(anti-aliased on the `min(r,g,b)` "whiteness" channel), removed a faint corner
watermark, cropped to content, squared/centered on a transparent canvas, and
downscaled to a crisp **512×512** PNG. Result verified on dark: pink mark with
transparent interior negative space, no white box.

## 5. Files created
- `apps/admin/public/brand/laundrykhalas-logo.png` (512×512, transparent)
- `apps/facility-dashboard/public/brand/laundrykhalas-logo.png` (512×512, transparent)

## 6. Files modified
- `apps/admin/components/dashboard/shell/Brand.tsx` — `BrandMark` now renders
  `<img src="/brand/laundrykhalas-logo.png" alt="LaundryKhalas">` (`h-9 w-9`,
  `object-contain`, no background tile) instead of the rose-tile SVG.
- `apps/facility-dashboard/components/shell/Brand.tsx` — same change.

`BrandWordmark` (mark + "LaundryKhalas" + subtitle) is unchanged in structure, so
the admin subtitle stays **"Command Center"** and facility stays **"Partner Portal"**.

## 7. UI surfaces affected (via shared BrandMark)
- Admin: sidebar brand (`Sidebar.tsx`, incl. collapsed → icon-only) + login page.
- Facility: desktop sidebar (`FacilityDesktopShell.tsx`), mobile header
  (`FacilityHeader.tsx`, `md:hidden`) + login page.

## 8. What is mock-only / live
No integrations touched. Static asset only.

## 9. Dynamic facility name — preserved
`FacilityHeader.tsx` still resolves the real facility name from
`facilityApi.me()` (`profile.name` → cached `user.facility_name` → "Facility
Dashboard" fallback, with skeleton). The logo is platform branding only and does
**not** replace the facility name. No changes to that logic.

## 10. Asset handling notes
- Referenced via the Next.js public path `/brand/laundrykhalas-logo.png` — **no**
  component references the Windows `Downloads` path.
- Plain `<img>` + inline `// eslint-disable-next-line @next/next/no-img-element`,
  matching the existing codebase idiom (`OrderPhotosPanel.tsx`, `OrderPhotoGrid.tsx`)
  and avoiding the next/image optimizer on the Cloudflare (`opennextjs`) deploy target.

## 11. Tests run & results
| App | typecheck | lint | build |
|-----|-----------|------|-------|
| admin | ✅ pass | ✅ pass (only pre-existing `useMemo` warning) | ✅ pass (isolated `LK_DIST_DIR`) |
| facility-dashboard | ✅ pass | ✅ pass (only pre-existing `useMemo` warning) | ✅ pass (isolated `LK_DIST_DIR`) |

Visual verification via headless Playwright (both dashboards auto-authenticated
in dev):
- Admin sidebar — light + **dark**: mark + "LaundryKhalas / COMMAND CENTER", crisp, no white box.
- Admin **collapsed** sidebar (dark): icon-only mark, centered — intentional.
- Facility sidebar — light + **dark**: mark + "LaundryKhalas / PARTNER PORTAL".
- Facility **mobile** top nav: mark + wordmark fit with bell/theme icons, no horizontal scroll, bottom nav intact.
- Admin mobile: hamburger drawer pattern (unchanged); no layout break.

## 12. Known limitations
- The mark's interior (bottle) is transparent by design, so on any surface the
  interior shows the surface colour (dark on dark theme, light on light) — matches
  the original logo intent; verified to read well on both.
- Full bilingual wordmark not used (its black Arabic text is unreadable on dark).

## 13. Security / privacy notes
None. Static image, no PII, no external calls.

## 14. How to verify manually
1. `cd apps/admin && npm run dev` → http://localhost:3000 — logo top-left of sidebar; toggle theme; collapse sidebar (icon-only).
2. `cd apps/facility-dashboard && npm run dev` → http://localhost:3010 — logo in sidebar; header still shows the real facility name; resize to mobile.

## 15. Next recommended step
Commit (asset + 2 component files). Optionally add a favicon / app-icon variant
from the same 512×512 mark.
