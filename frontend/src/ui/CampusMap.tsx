import { Maximize2, Minus, Plus } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { cn } from './cn'

export interface MapDecor {
  kind: 'road' | 'path' | 'green' | 'water' | 'gate'
  /** An exact outline (real building/road footprints aren't always rectangles). When present, this draws instead of the x/y/w/h rect. */
  d?: string
  x: number
  y: number
  w: number
  h: number
  r?: number
}

export type MapShape = { type: 'rect'; x: number; y: number; w: number; h: number; r?: number } | { type: 'path'; d: string; x: number; y: number; w: number; h: number }

export interface MapRegion {
  regionId: string
  label: string
  shape: MapShape
}

export type RegionState = 'OPEN' | 'AFFECTED' | 'CLOSED' | 'MAINTENANCE'

export interface RegionOverlay {
  state: RegionState
  /** A short count shown on the building, such as the number of open incidents. */
  badge?: number
  caption?: string
}

export interface MapMarker {
  id: string
  x: number
  y: number
  label: string
  tone: 'danger' | 'warning' | 'info' | 'success'
}

export interface CampusMapProps {
  viewBox: { w: number; h: number }
  decor: MapDecor[]
  regions: MapRegion[]
  overlays: Record<string, RegionOverlay>
  selectedId: string | null
  onSelect: (regionId: string | null) => void
  markers?: MapMarker[]
  className?: string
}

const DECOR_CLASS: Record<MapDecor['kind'], string> = {
  green: 'fill-success-soft',
  road: 'fill-surface-3',
  path: 'fill-surface-2',
  water: 'fill-info-soft',
  gate: 'fill-accent',
}

const REGION_CLASS: Record<RegionState, string> = {
  OPEN: 'fill-surface stroke-line-strong',
  AFFECTED: 'fill-warning-soft stroke-warning',
  CLOSED: 'fill-danger-soft stroke-danger',
  MAINTENANCE: 'fill-info-soft stroke-info',
}

const STATE_TEXT: Record<RegionState, string> = { OPEN: 'Open', AFFECTED: 'Affected', CLOSED: 'Closed', MAINTENANCE: 'Under maintenance' }
const STATE_GLYPH: Record<RegionState, string> = { OPEN: '', AFFECTED: '!', CLOSED: 'x', MAINTENANCE: 'M' }

const MARKER_FILL = { danger: 'fill-danger', warning: 'fill-warning', info: 'fill-info', success: 'fill-success' }

const MIN_ZOOM = 1
const MAX_ZOOM = 4
const DRAG_THRESHOLD = 5


const LABEL_SIZE = 27
const CAPTION_SIZE = 19

/** Splits a label on spaces so each line fits the building width, at most two lines. */
function wrapLabel(label: string, width: number): string[] {
  const perLine = Math.max(6, Math.floor((width - 36) / (LABEL_SIZE * 0.56)))
  const words = label.split(' ')
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    if (current && `${current} ${word}`.length > perLine) {
      lines.push(current)
      current = word
    } else {
      current = current ? `${current} ${word}` : word
    }
  }
  if (current) lines.push(current)
  if (lines.length > 2) return [lines[0]!, `${lines.slice(1).join(' ').slice(0, perLine - 1)}...`]
  return lines
}

function clip(text: string, width: number): string {
  const perLine = Math.floor((width - 36) / (CAPTION_SIZE * 0.52))
  return text.length > perLine ? `${text.slice(0, Math.max(3, perLine - 1))}...` : text
}

interface View {
  k: number
  x: number
  y: number
}

export function CampusMap({ viewBox, decor, regions, overlays, selectedId, onSelect, markers = [], className }: CampusMapProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const hatchId = useId()
  const [view, setView] = useState<View>({ k: 1, x: 0, y: 0 })
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const gesture = useRef({ moved: 0, pinch: 0 })

  const clamp = useCallback(
    (next: View): View => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next.k))
      return {
        k,
        x: Math.min(0, Math.max(viewBox.w - viewBox.w * k, next.x)),
        y: Math.min(0, Math.max(viewBox.h - viewBox.h * k, next.y)),
      }
    },
    [viewBox.h, viewBox.w],
  )

  const unitsPerPixel = () => {
    const width = svgRef.current?.getBoundingClientRect().width
    return width ? viewBox.w / width : 1
  }

  const zoomAround = useCallback(
    (factor: number, cx: number, cy: number) =>
      setView((current) => {
        const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current.k * factor))
        const ratio = k / current.k
        return clamp({ k, x: cx - (cx - current.x) * ratio, y: cy - (cy - current.y) * ratio })
      }),
    [clamp],
  )

  // React attaches wheel listeners as passive, so the page-scroll guard has to be added by hand.
  useEffect(() => {
    const element = svgRef.current
    if (!element) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const rect = element.getBoundingClientRect()
      const scale = viewBox.w / rect.width
      zoomAround(event.deltaY < 0 ? 1.15 : 1 / 1.15, (event.clientX - rect.left) * scale, (event.clientY - rect.top) * scale)
    }
    element.addEventListener('wheel', onWheel, { passive: false })
    return () => element.removeEventListener('wheel', onWheel)
  }, [viewBox.w, zoomAround])

  const onPointerDown = (event: PointerEvent) => {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    gesture.current = { moved: 0, pinch: 0 }
  }

  const onPointerMove = (event: PointerEvent) => {
    const previous = pointers.current.get(event.pointerId)
    if (!previous) return
    const current = { x: event.clientX, y: event.clientY }
    pointers.current.set(event.pointerId, current)
    const scale = unitsPerPixel()

    if (pointers.current.size === 1) {
      const dx = current.x - previous.x
      const dy = current.y - previous.y
      gesture.current.moved += Math.abs(dx) + Math.abs(dy)
      if (gesture.current.moved > DRAG_THRESHOLD) setView((v) => clamp({ ...v, x: v.x + dx * scale, y: v.y + dy * scale }))
    } else if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }]
      const distance = Math.hypot(a.x - b.x, a.y - b.y)
      const rect = svgRef.current?.getBoundingClientRect()
      if (gesture.current.pinch && rect) {
        zoomAround(distance / gesture.current.pinch, ((a.x + b.x) / 2 - rect.left) * scale, ((a.y + b.y) / 2 - rect.top) * scale)
      }
      gesture.current.pinch = distance
      gesture.current.moved = DRAG_THRESHOLD + 1
    }
  }

  const onPointerEnd = (event: PointerEvent) => {
    pointers.current.delete(event.pointerId)
    gesture.current.pinch = 0
  }

  const choose = (regionId: string) => {
    if (gesture.current.moved > DRAG_THRESHOLD) return
    onSelect(regionId === selectedId ? null : regionId)
  }

  const onRegionKey = (event: KeyboardEvent, regionId: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(regionId === selectedId ? null : regionId)
    }
  }

  const centre = { x: viewBox.w / 2, y: viewBox.h / 2 }

  return (
    <div className={cn('relative overflow-hidden rounded-lg border border-line bg-surface-2', className)}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${viewBox.w} ${viewBox.h}`}
        role="group"
        aria-label="Campus map. Drag to move, pinch or use the buttons to zoom, and tab to a building to select it."
        className="block h-auto w-full touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onPointerLeave={onPointerEnd}
      >
        <defs>
          <pattern id={hatchId} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="10" strokeWidth="3" className="stroke-danger" opacity="0.45" />
          </pattern>
        </defs>
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {decor.map((item, index) =>
            item.d ? (
              <path key={index} d={item.d} className={DECOR_CLASS[item.kind]} />
            ) : (
              <rect key={index} x={item.x} y={item.y} width={item.w} height={item.h} rx={item.r ?? 0} className={DECOR_CLASS[item.kind]} />
            ),
          )}

          {regions.map((region) => {
            const overlay = overlays[region.regionId] ?? { state: 'OPEN' as RegionState }
            const { x, y, w, h } = region.shape
            const r = region.shape.type === 'rect' ? region.shape.r : undefined
            const selected = region.regionId === selectedId
            const caption = overlay.caption ? `, ${overlay.caption}` : ''
            const regionClass = cn(REGION_CLASS[overlay.state], selected && 'stroke-accent')
            return (
              <g
                key={region.regionId}
                role="button"
                tabIndex={0}
                aria-pressed={selected}
                aria-label={`${region.label}, ${STATE_TEXT[overlay.state]}${caption}`}
                data-testid={`region-${region.regionId}`}
                data-state={overlay.state}
                className="cursor-pointer outline-none focus-visible:[&>rect:first-child]:stroke-accent focus-visible:[&>path:first-child]:stroke-accent"
                onClick={() => choose(region.regionId)}
                onKeyDown={(event) => onRegionKey(event, region.regionId)}
              >
                {region.shape.type === 'path' ? (
                  <path d={region.shape.d} strokeWidth={selected ? 5 : 2} className={regionClass} />
                ) : (
                  <rect x={x} y={y} width={w} height={h} rx={r ?? 10} strokeWidth={selected ? 5 : 2} className={regionClass} />
                )}
                {overlay.state === 'CLOSED' ? (
                  region.shape.type === 'path' ? (
                    <path d={region.shape.d} fill={`url(#${hatchId})`} pointerEvents="none" />
                  ) : (
                    <rect x={x} y={y} width={w} height={h} rx={r ?? 10} fill={`url(#${hatchId})`} pointerEvents="none" />
                  )
                ) : null}
                {wrapLabel(region.label, w).map((line, index) => (
                  <text key={index} x={x + 18} y={y + 38 + index * (LABEL_SIZE + 4)} fontSize={LABEL_SIZE} fontWeight={650} className="fill-ink" pointerEvents="none">
                    {line}
                  </text>
                ))}
                <text x={x + 18} y={y + 38 + wrapLabel(region.label, w).length * (LABEL_SIZE + 4) + 4} fontSize={CAPTION_SIZE} className="fill-muted" pointerEvents="none">
                  {clip(`${STATE_TEXT[overlay.state]}${overlay.caption ? ` · ${overlay.caption}` : ''}`, w)}
                </text>
                {overlay.state !== 'OPEN' ? (
                  <g pointerEvents="none">
                    <circle cx={x + w - 26} cy={y + 26} r={17} className="fill-surface stroke-ink" strokeWidth={2} />
                    <text x={x + w - 26} y={y + 33} fontSize={20} fontWeight={700} textAnchor="middle" className="fill-ink">
                      {STATE_GLYPH[overlay.state]}
                    </text>
                  </g>
                ) : null}
                {overlay.badge ? (
                  <g pointerEvents="none">
                    <circle cx={x + w - 28} cy={y + h - 28} r={19} className="fill-danger" />
                    <text x={x + w - 28} y={y + h - 21} fontSize={21} fontWeight={700} textAnchor="middle" className="fill-accent-contrast">
                      {overlay.badge}
                    </text>
                  </g>
                ) : null}
              </g>
            )
          })}

          {markers.map((marker) => (
            <g key={marker.id} data-testid={`marker-${marker.id}`}>
              <title>{marker.label}</title>
              <circle cx={marker.x} cy={marker.y} r={13} className={cn(MARKER_FILL[marker.tone], 'stroke-surface')} strokeWidth={3} />
            </g>
          ))}
        </g>
      </svg>

      <div className="absolute bottom-3 right-3 flex flex-col overflow-hidden rounded-md border border-line-strong bg-surface shadow-card">
        <button type="button" aria-label="Zoom in" onClick={() => zoomAround(1.4, centre.x, centre.y)} className="grid size-11 place-items-center hover:bg-surface-2">
          <Plus aria-hidden="true" className="size-5" />
        </button>
        <button type="button" aria-label="Zoom out" onClick={() => zoomAround(1 / 1.4, centre.x, centre.y)} className="grid size-11 place-items-center border-t border-line hover:bg-surface-2">
          <Minus aria-hidden="true" className="size-5" />
        </button>
        <button type="button" aria-label="Reset view" onClick={() => setView({ k: 1, x: 0, y: 0 })} className="grid size-11 place-items-center border-t border-line hover:bg-surface-2">
          <Maximize2 aria-hidden="true" className="size-5" />
        </button>
      </div>
    </div>
  )
}

/** The legend pairs each state with its symbol and a word, so the map never relies on colour alone. */
export function MapLegend({ states = ['OPEN', 'AFFECTED', 'CLOSED', 'MAINTENANCE'] as RegionState[] }: { states?: RegionState[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted" aria-label="Map legend">
      {states.map((state) => (
        <li key={state} className="flex items-center gap-2">
          <span aria-hidden="true" className={cn('grid size-5 place-items-center rounded-sm border text-[0.625rem] font-bold text-ink', REGION_CLASS[state].replace('fill-', 'bg-').replace('stroke-', 'border-'))}>
            {STATE_GLYPH[state]}
          </span>
          {STATE_TEXT[state]}
        </li>
      ))}
    </ul>
  )
}
