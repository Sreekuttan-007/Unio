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
  viewBox?: { w: number; h: number }
  decor?: MapDecor[]
  regions?: MapRegion[]
  overlays?: Record<string, RegionOverlay>
  selectedId: string | null
  onSelect: (regionId: string | null) => void
  markers?: MapMarker[]
  className?: string
}

const REGION_CLASS: Record<RegionState, string> = {
  OPEN: 'fill-surface stroke-line-strong',
  AFFECTED: 'fill-warning-soft stroke-warning',
  CLOSED: 'fill-danger-soft stroke-danger',
  MAINTENANCE: 'fill-info-soft stroke-info',
}

const DECOR_CLASS: Record<MapDecor['kind'], string> = {
  green: 'fill-success-soft',
  road: 'fill-surface-3',
  path: 'fill-surface-2',
  water: 'fill-info-soft',
  gate: 'fill-accent',
}

const STATE_TEXT: Record<RegionState, string> = {
  OPEN: 'Open',
  AFFECTED: 'Affected',
  CLOSED: 'Closed',
  MAINTENANCE: 'Under maintenance',
}

const LABEL_SIZE = 27
const CAPTION_SIZE = 19

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

const STATE_GLYPH: Record<RegionState, string> = {
  OPEN: '',
  AFFECTED: '!',
  CLOSED: 'x',
  MAINTENANCE: 'M',
}

const MARKER_FILL = {
  danger: 'fill-danger',
  warning: 'fill-warning',
  info: 'fill-info',
  success: 'fill-success',
}

const MIN_ZOOM = 0.8
const MAX_ZOOM = 4
const DRAG_THRESHOLD = 5

interface DataDrivenMapLayerProps {
  decor: MapDecor[]
  regions: MapRegion[]
  overlays: Record<string, RegionOverlay>
  selectedId: string | null
  markers: MapMarker[]
  hatchId: string
  onChoose: (regionId: string) => void
  onRegionKey: (event: KeyboardEvent, regionId: string) => void
}

function DataDrivenMapLayer({ decor, regions, overlays, selectedId, markers, hatchId, onChoose, onRegionKey }: DataDrivenMapLayerProps) {
  return (
    <>
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
            onClick={() => onChoose(region.regionId)}
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
    </>
  )
}

const BUILDING_CENTRES: Record<string, { x: number; y: number }> = {
  "BMS-12": {
    "x": 1025,
    "y": 440
  },
  "BLK-13A": {
    "x": 980,
    "y": 337
  },
  "SRMIST-ADMIN": {
    "x": 1080,
    "y": 356
  },
  "BLK-13B": {
    "x": 938,
    "y": 575
  },
  "PG-1": {
    "x": 1035,
    "y": 548
  },
  "PG-2": {
    "x": 1033,
    "y": 614
  },
  "ELEC-1": {
    "x": 695,
    "y": 576
  },
  "ELEC-2": {
    "x": 819,
    "y": 572
  },
  "UNK-T2": {
    "x": 846,
    "y": 523
  },
  "EEC-MAIN": {
    "x": 413,
    "y": 530
  },
  "UNK-T1": {
    "x": 298,
    "y": 439
  },
  "PGCM-18": {
    "x": 642,
    "y": 855
  },
  "UNK-T3": {
    "x": 542,
    "y": 798
  },
  "ACAD-1": {
    "x": 1381,
    "y": 684
  },
  "ACAD-2": {
    "x": 1459,
    "y": 664
  },
  "ACAD-4": {
    "x": 1202,
    "y": 779
  },
  "GH": {
    "x": 1177,
    "y": 555
  },
  "SRM-PRIME": {
    "x": 1272,
    "y": 569
  },
  "DENTAL-COL": {
    "x": 1007,
    "y": 676
  },
  "BLK-10": {
    "x": 953,
    "y": 722
  },
  "DENTAL-HOSP": {
    "x": 1010,
    "y": 802
  },
  "UNK-M1": {
    "x": 978,
    "y": 892
  },
  "BOYS-8": {
    "x": 1221,
    "y": 245
  },
  "BLK-9": {
    "x": 1228,
    "y": 360
  },
  "UNK-H1": {
    "x": 1385,
    "y": 210
  },
  "LADIES-20": {
    "x": 169,
    "y": 714
  },
  "CHELLAMMAL-21": {
    "x": 192,
    "y": 822
  },
  "SIVASAKTHI": {
    "x": 339,
    "y": 820
  },
  "UNK-H2": {
    "x": 324,
    "y": 701
  },
  "IST-8": {
    "x": 1410,
    "y": 373
  },
  "UNK-C1": {
    "x": 1377,
    "y": 255
  },
  "WORKSHOP": {
    "x": 1423,
    "y": 143
  },
  "BLK-3": {
    "x": 1279,
    "y": 772
  },
  "BLK-23N": {
    "x": 257,
    "y": 597
  },
  "BLK-23S": {
    "x": 173,
    "y": 635
  },
  "LAWN": {
    "x": 1029,
    "y": 233
  },
  "EEC-COURT": {
    "x": 409,
    "y": 534
  },
  "OAT": {
    "x": 579,
    "y": 750
  },
  "SPORTS": {
    "x": 1544,
    "y": 685
  }
}

const BUILDING_ALIASES: Record<string, string> = {
  "bld-arb": "EEC-MAIN",
  "bld-bhb": "ACAD-1",
  "bld-rmb": "ACAD-2",
  "bld-rlb": "ACAD-4",
  "bld-lib": "PG-1",
  "bld-adm": "SRMIST-ADMIN",
  "bld-caf": "SPORTS",
  "bld-klh": "BOYS-8"
}

interface View {
  k: number
  x: number
  y: number
}

export function CampusMap({
  viewBox = { w: 1600, h: 1195 },
  decor,
  regions,
  overlays = {},
  selectedId,
  onSelect,
  markers = [],
  className,
}: CampusMapProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const gridId = useId()
  const hatchId = useId()
  const [view, setView] = useState<View>({ k: 1, x: 0, y: 0 })
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const gesture = useRef({ moved: 0, pinch: 0 })

  const vb = { w: viewBox?.w || 1600, h: viewBox?.h || 1195 }

  const clamp = useCallback(
    (next: View): View => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next.k))
      return {
        k,
        x: Math.min(0, Math.max(vb.w - vb.w * k, next.x)),
        y: Math.min(0, Math.max(vb.h - vb.h * k, next.y)),
      }
    },
    [vb.h, vb.w],
  )

  const unitsPerPixel = () => {
    const width = svgRef.current?.getBoundingClientRect().width
    return width ? vb.w / width : 1
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

  useEffect(() => {
    const element = svgRef.current
    if (!element) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const rect = element.getBoundingClientRect()
      const scale = vb.w / rect.width
      zoomAround(event.deltaY < 0 ? 1.15 : 1 / 1.15, (event.clientX - rect.left) * scale, (event.clientY - rect.top) * scale)
    }
    element.addEventListener('wheel', onWheel, { passive: false })
    return () => element.removeEventListener('wheel', onWheel)
  }, [vb.w, zoomAround])

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
      if (gesture.current.moved > DRAG_THRESHOLD) {
        setView((v) => clamp({ ...v, x: v.x + dx * scale, y: v.y + dy * scale }))
      }
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
    const nextId = regionId === selectedId ? null : regionId
    onSelect(nextId)
    if (typeof window !== 'undefined') {
      const g = document.getElementById(regionId)
      g?.dispatchEvent(
        new CustomEvent('building-select', {
          bubbles: true,
          detail: { id: regionId, name: g?.getAttribute('data-name'), zone: g?.getAttribute('data-zone') },
        }),
      )
    }
  }

  const onRegionKey = (event: KeyboardEvent, regionId: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      choose(regionId)
    }
  }

  const centre = { x: vb.w / 2, y: vb.h / 2 }

  const resolvedOverlays: { id: string; overlay: RegionOverlay; pos: { x: number; y: number } }[] = []
  for (const [key, ov] of Object.entries(overlays)) {
    const targetId = BUILDING_ALIASES[key] ?? key
    const pos = BUILDING_CENTRES[targetId]
    if (pos) {
      resolvedOverlays.push({ id: targetId, overlay: ov, pos })
    }
  }

  return (
    <div className={cn('relative overflow-hidden rounded-2xl border border-line/70 bg-surface-2/80 shadow-card backdrop-blur-xs', className)}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${vb.w} ${vb.h}`}
        role="group"
        aria-label="Campus site map. Drag to pan, scroll to zoom, and tap any building to inspect details."
        className="campus-map-svg block h-auto w-full touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
        onPointerLeave={onPointerEnd}
      >
        <defs>
          <pattern id={gridId} width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0V24" fill="none" className="stroke-map-grid" strokeWidth="1" />
          </pattern>
          <pattern id={hatchId} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="10" strokeWidth="3" className="stroke-danger" opacity="0.45" />
          </pattern>
        </defs>

        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {regions !== undefined || decor !== undefined ? (
            <DataDrivenMapLayer
              decor={decor ?? []}
              regions={regions ?? []}
              overlays={overlays}
              selectedId={selectedId}
              markers={markers}
              hatchId={hatchId}
              onChoose={choose}
              onRegionKey={onRegionKey}
            />
          ) : (
            <>
          <rect className="bg" width="1600" height="1195"/>
<rect width="1600" height="1195" fill={`url(#${gridId})`}/>

{/*  ROADS & PARKING  */}
<g id="roads">
<polygon className="road" points="0,822 120,835 400,935 700,980 860,1000 1100,1000 1400,985 1600,945 1600,1005 1400,1042 1100,1052 870,1054 700,1036 400,962 0,882"/>
<polygon className="road" points="908,105 1325,92 1345,120 1325,125 908,150"/>
<polygon className="road" points="1330,165 1362,165 1375,470 1328,470"/>
<polygon className="road" points="1315,445 1342,448 1344,880 1318,880"/>
<polygon className="road" points="1442,0 1478,0 1600,230 1600,278 1440,60"/>
<polygon className="road" points="1112,365 1140,365 1140,972 1112,972"/>
<polygon className="road" points="258,648 500,596 500,520 545,535 640,545 645,598 760,606 900,628 900,650 1138,650 1138,682 905,682 905,975 862,975 862,832 832,832 832,690 420,690 258,665"/>
<polygon className="park" points="770,445 905,440 905,520 795,520 760,490"/>
<polygon className="park" points="895,885 1110,885 1110,975 905,975"/>
<polygon className="road" points="415,950 445,950 432,1080 400,1080"/>
<polygon className="road" points="1225,1030 1250,1030 1247,1085 1222,1085"/>
<rect className="road" x="920" y="1050" width="45" height="43"/>
</g>

{/*  ENGINEERING CAMPUS  */}
<g id="BMS-12" className={cn('b eng', selectedId === 'BMS-12' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BMS-12'} onClick={() => choose('BMS-12')} onKeyDown={(e) => onRegionKey(e, 'BMS-12')} data-id="BMS-12" data-name="New BMS Block" data-map-no="12" data-zone="engineering"><rect x="938" y="376" width="174" height="127"/><text className="lbl" x="1023" y="452" fontSize="24">12</text></g>
<g id="BLK-13A" className={cn('b eng', selectedId === 'BLK-13A' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-13A'} onClick={() => choose('BLK-13A')} onKeyDown={(e) => onRegionKey(e, 'BLK-13A')} data-id="BLK-13A" data-name="Block 13 (north)" data-map-no="13" data-zone="engineering"><rect x="920" y="312" width="120" height="50"/><text className="lbl" x="983" y="347" fontSize="24">13</text></g>
<g id="SRMIST-ADMIN" className={cn('b eng', selectedId === 'SRMIST-ADMIN' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'SRMIST-ADMIN'} onClick={() => choose('SRMIST-ADMIN')} onKeyDown={(e) => onRegionKey(e, 'SRMIST-ADMIN')} data-id="SRMIST-ADMIN" data-name="SRMIST Admin Block" data-zone="engineering"><rect x="1050" y="335" width="60" height="42"/></g>
<g id="BLK-13B" className={cn('b eng', selectedId === 'BLK-13B' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-13B'} onClick={() => choose('BLK-13B')} onKeyDown={(e) => onRegionKey(e, 'BLK-13B')} data-id="BLK-13B" data-name="Block 13 (south)" data-map-no="13" data-zone="engineering"><rect x="900" y="522" width="75" height="106"/><text className="lbl" x="927" y="590" fontSize="24">13</text></g>
<g id="PG-1" className={cn('b eng', selectedId === 'PG-1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'PG-1'} onClick={() => choose('PG-1')} onKeyDown={(e) => onRegionKey(e, 'PG-1')} data-id="PG-1" data-name="PG Block 1" data-map-no="14" data-zone="engineering"><rect x="978" y="535" width="114" height="25"/><text className="lbl" x="1035" y="553" fontSize="14">PG BLOCK 1</text></g>
<g id="PG-2" className={cn('b eng', selectedId === 'PG-2' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'PG-2'} onClick={() => choose('PG-2')} onKeyDown={(e) => onRegionKey(e, 'PG-2')} data-id="PG-2" data-name="PG Block 2" data-zone="engineering"><polygon points="975,595 1075,595 1075,598 1090,598 1090,632 975,632"/><text className="lbl" x="1030" y="620" fontSize="15">PG BLOCK 2</text></g>
<text className="lbl" x="1035" y="585" fontSize="22">14</text>
<g id="ELEC-1" className={cn('b eng', selectedId === 'ELEC-1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'ELEC-1'} onClick={() => choose('ELEC-1')} onKeyDown={(e) => onRegionKey(e, 'ELEC-1')} data-id="ELEC-1" data-name="Electronics Block 1" data-zone="engineering"><rect x="645" y="548" width="100" height="55"/><text className="lbl" x="695" y="574" fontSize="13">ELECTRONICS</text><text className="lbl" x="695" y="591" fontSize="13">BLOCK - 1</text></g>
<g id="ELEC-2" className={cn('b eng', selectedId === 'ELEC-2' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'ELEC-2'} onClick={() => choose('ELEC-2')} onKeyDown={(e) => onRegionKey(e, 'ELEC-2')} data-id="ELEC-2" data-name="Electronics Block 2" data-zone="engineering"><rect x="755" y="537" width="127" height="70"/><text className="lbl" x="819" y="572" fontSize="14">ELECTRONICS</text><text className="lbl" x="819" y="590" fontSize="14">BLOCK - 2</text></g>
<g id="UNK-T2" className={cn('b eng', selectedId === 'UNK-T2' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-T2'} onClick={() => choose('UNK-T2')} onKeyDown={(e) => onRegionKey(e, 'UNK-T2')} data-id="UNK-T2" data-name="Unlabeled" data-unlabeled="true" data-zone="engineering"><rect x="810" y="505" width="72" height="35"/></g>
<g id="EEC-MAIN" className={cn('b eng', selectedId === 'EEC-MAIN' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'EEC-MAIN'} onClick={() => choose('EEC-MAIN')} onKeyDown={(e) => onRegionKey(e, 'EEC-MAIN')} data-id="EEC-MAIN" data-name="EEC Main Block" data-zone="engineering"><path fillRule="evenodd" d="M340,490 L380,450 L450,450 L495,500 L495,590 L450,600 L400,610 L340,605 L330,540 Z M378,498 L440,498 L440,520 L425,520 L425,545 L440,545 L440,570 L378,570 Z"/></g>
<text className="lbl" x="438" y="366" fontSize="16">SRM EASWARI</text><text className="lbl" x="438" y="388" fontSize="16">ENGINEERING COLLEGE</text><text className="lbl" x="438" y="410" fontSize="16">(EEC) MAIN BLOCK</text>
<g id="UNK-T1" className={cn('b eng', selectedId === 'UNK-T1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-T1'} onClick={() => choose('UNK-T1')} onKeyDown={(e) => onRegionKey(e, 'UNK-T1')} data-id="UNK-T1" data-name="Unlabeled" data-unlabeled="true" data-zone="engineering"><rect x="275" y="415" width="45" height="47"/></g>
<g id="PGCM-18" className={cn('b eng', selectedId === 'PGCM-18' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'PGCM-18'} onClick={() => choose('PGCM-18')} onKeyDown={(e) => onRegionKey(e, 'PGCM-18')} data-id="PGCM-18" data-name="PG, Civil &amp; Mechanical Block" data-map-no="18" data-zone="engineering"><polygon points="468,805 520,800 560,820 690,845 815,885 810,910 700,890 560,860 468,832"/><text className="lbl" x="640" y="865" fontSize="15" transform="rotate(15 640 865)">PG, CIVIL &amp; MECHANICAL BLOCK</text></g>
<text className="lbl" x="506" y="829" fontSize="22">18</text>
<g id="UNK-T3" className={cn('b eng', selectedId === 'UNK-T3' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-T3'} onClick={() => choose('UNK-T3')} onKeyDown={(e) => onRegionKey(e, 'UNK-T3')} data-id="UNK-T3" data-name="Unlabeled" data-unlabeled="true" data-zone="engineering"><rect x="513" y="780" width="57" height="35"/></g>
<g id="ACAD-1" className={cn('b eng', selectedId === 'ACAD-1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'ACAD-1'} onClick={() => choose('ACAD-1')} onKeyDown={(e) => onRegionKey(e, 'ACAD-1')} data-id="ACAD-1" data-name="Academic Block 1" data-zone="engineering"><polygon points="1368,532 1414,532 1414,836 1348,836 1350,770 1368,748"/><text className="lbl" x="1385" y="685" fontSize="16" transform="rotate(-90 1385 685)">ACADEMIC BLOCK 1</text></g>
<g id="ACAD-2" className={cn('b eng', selectedId === 'ACAD-2' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'ACAD-2'} onClick={() => choose('ACAD-2')} onKeyDown={(e) => onRegionKey(e, 'ACAD-2')} data-id="ACAD-2" data-name="Academic Block 2" data-zone="engineering"><polygon points="1442,502 1476,502 1476,812 1450,826 1442,820"/><text className="lbl" x="1465" y="665" fontSize="16" transform="rotate(-90 1465 665)">ACADEMIC BLOCK 2</text></g>
<g id="ACAD-4" className={cn('b eng', selectedId === 'ACAD-4' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'ACAD-4'} onClick={() => choose('ACAD-4')} onKeyDown={(e) => onRegionKey(e, 'ACAD-4')} data-id="ACAD-4" data-name="Academic Block 4" data-zone="engineering"><polygon points="1168,707 1235,707 1235,850 1170,850"/><text className="lbl" x="1196" y="780" fontSize="12" transform="rotate(-90 1196 780)">ACADEMIC BLOCK 4</text></g>

{/*  MEDICAL CAMPUS & DENTAL  */}
<g id="GH" className={cn('b med', selectedId === 'GH' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'GH'} onClick={() => choose('GH')} onKeyDown={(e) => onRegionKey(e, 'GH')} data-id="GH" data-name="General Hospital" data-zone="medical"><rect x="1138" y="442" width="77" height="226"/><text className="lbl w" x="1172" y="555" fontSize="16" transform="rotate(-90 1172 555)">GENERAL HOSPITAL</text></g>
<g id="SRM-PRIME" className={cn('b med', selectedId === 'SRM-PRIME' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'SRM-PRIME'} onClick={() => choose('SRM-PRIME')} onKeyDown={(e) => onRegionKey(e, 'SRM-PRIME')} data-id="SRM-PRIME" data-name="General Hospital / SRM Prime Hospital" data-zone="medical"><rect x="1218" y="465" width="107" height="207"/><text className="lbl w" x="1262" y="568" fontSize="15" transform="rotate(-90 1262 568)">GENERAL HOSPITAL /</text><text className="lbl w" x="1284" y="568" fontSize="15" transform="rotate(-90 1284 568)">SRM PRIME HOSPITAL</text></g>
<g id="DENTAL-COL" className={cn('b med', selectedId === 'DENTAL-COL' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'DENTAL-COL'} onClick={() => choose('DENTAL-COL')} onKeyDown={(e) => onRegionKey(e, 'DENTAL-COL')} data-id="DENTAL-COL" data-name="SRM Dental College" data-zone="medical"><rect x="924" y="650" width="166" height="52"/><text className="lbl w" x="1000" y="672" fontSize="16">SRM DENTAL</text><text className="lbl w" x="1040" y="692" fontSize="16">COLLEGE</text></g>
<g id="BLK-10" className={cn('b med', selectedId === 'BLK-10' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-10'} onClick={() => choose('BLK-10')} onKeyDown={(e) => onRegionKey(e, 'BLK-10')} data-id="BLK-10" data-name="Block 10" data-map-no="10" data-zone="medical"><rect x="925" y="703" width="55" height="38"/><text className="lbl w" x="952" y="731" fontSize="24">10</text></g>
<g id="DENTAL-HOSP" className={cn('b med', selectedId === 'DENTAL-HOSP' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'DENTAL-HOSP'} onClick={() => choose('DENTAL-HOSP')} onKeyDown={(e) => onRegionKey(e, 'DENTAL-HOSP')} data-id="DENTAL-HOSP" data-name="Dental Hospital" data-map-no="15" data-zone="medical"><polygon points="927,797 1000,797 1000,725 1092,725 1092,797 1065,797 1065,878 927,878"/><text className="lbl w" x="1050" y="785" fontSize="24">15</text><text className="lbl w" x="985" y="821" fontSize="18">DENTAL</text><text className="lbl w" x="985" y="843" fontSize="18">HOSPITAL</text></g>
<g id="UNK-M1" className={cn('b med', selectedId === 'UNK-M1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-M1'} onClick={() => choose('UNK-M1')} onKeyDown={(e) => onRegionKey(e, 'UNK-M1')} data-id="UNK-M1" data-name="Unlabeled" data-unlabeled="true" data-zone="medical"><rect x="950" y="878" width="55" height="27"/></g>

{/*  HOSTELS  */}
<g id="BOYS-8" className={cn('b host', selectedId === 'BOYS-8' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BOYS-8'} onClick={() => choose('BOYS-8')} onKeyDown={(e) => onRegionKey(e, 'BOYS-8')} data-id="BOYS-8" data-name="Boys Hostel" data-map-no="8" data-zone="hostel"><polygon points="1158,143 1230,145 1228,190 1190,192 1192,215 1225,205 1225,260 1262,262 1292,300 1290,347 1170,318 1170,285 1150,280"/><text className="lbl" x="1178" y="250" fontSize="24">8</text></g>
<text className="lbl" x="1268" y="223" fontSize="16">BOYS</text><text className="lbl" x="1268" y="245" fontSize="16">HOSTEL</text>
<g id="BLK-9" className={cn('b host2', selectedId === 'BLK-9' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-9'} onClick={() => choose('BLK-9')} onKeyDown={(e) => onRegionKey(e, 'BLK-9')} data-id="BLK-9" data-name="Block 9" data-map-no="9" data-zone="hostel"><polygon points="1168,322 1290,348 1286,398 1186,398 1166,380"/><text className="lbl" x="1225" y="362" fontSize="24">9</text></g>
<g id="UNK-H1" className={cn('b host2', selectedId === 'UNK-H1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-H1'} onClick={() => choose('UNK-H1')} onKeyDown={(e) => onRegionKey(e, 'UNK-H1')} data-id="UNK-H1" data-name="Unlabeled" data-unlabeled="true" data-zone="hostel"><rect x="1365" y="185" width="40" height="50"/></g>
<g id="LADIES-20" className={cn('b host2', selectedId === 'LADIES-20' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'LADIES-20'} onClick={() => choose('LADIES-20')} onKeyDown={(e) => onRegionKey(e, 'LADIES-20')} data-id="LADIES-20" data-name="Hostel Block 20" data-map-no="20" data-zone="hostel"><polygon points="108,645 145,645 165,628 195,645 237,655 255,685 240,710 248,740 245,780 215,790 175,800 140,790 95,780 85,750 95,720 82,695 90,665"/><text className="lbl" x="164" y="724" fontSize="26">20</text></g>
<g id="CHELLAMMAL-21" className={cn('b host2', selectedId === 'CHELLAMMAL-21' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'CHELLAMMAL-21'} onClick={() => choose('CHELLAMMAL-21')} onKeyDown={(e) => onRegionKey(e, 'CHELLAMMAL-21')} data-id="CHELLAMMAL-21" data-name="Chellammal Ladies Hostel" data-map-no="21" data-zone="hostel"><rect x="133" y="795" width="117" height="53"/><text className="lbl" x="192" y="816" fontSize="14">CHELLAMMAL</text><text className="lbl" x="192" y="834" fontSize="14">LADIES HOSTEL</text></g>
<text className="lbl" x="195" y="867" fontSize="22">21</text>
<g id="SIVASAKTHI" className={cn('b host2', selectedId === 'SIVASAKTHI' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'SIVASAKTHI'} onClick={() => choose('SIVASAKTHI')} onKeyDown={(e) => onRegionKey(e, 'SIVASAKTHI')} data-id="SIVASAKTHI" data-name="Sivasakthi Ladies Hostel" data-zone="hostel"><rect x="273" y="790" width="132" height="60"/><text className="lbl" x="339" y="812" fontSize="14">SIVASAKTHI</text><text className="lbl" x="339" y="830" fontSize="14">LADIES HOSTEL</text></g>
<g id="UNK-H2" className={cn('b host2', selectedId === 'UNK-H2' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-H2'} onClick={() => choose('UNK-H2')} onKeyDown={(e) => onRegionKey(e, 'UNK-H2')} data-id="UNK-H2" data-name="Unlabeled" data-unlabeled="true" data-zone="hostel"><polygon points="295,685 340,672 357,680 345,705 310,708 305,730 290,730"/></g>

{/*  COMMONS & UTILITIES  */}
<g id="IST-8" className={cn('b com', selectedId === 'IST-8' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'IST-8'} onClick={() => choose('IST-8')} onKeyDown={(e) => onRegionKey(e, 'IST-8')} data-id="IST-8" data-name="Institute of Science &amp; Technology" data-map-no="8" data-zone="commons"><polygon points="1362,270 1395,268 1395,300 1400,395 1470,425 1470,450 1425,478 1400,455 1385,448 1350,445 1350,405 1362,380"/><text className="lbl" x="1373" y="363" fontSize="24">8</text></g>
<text className="lbl" x="1483" y="305" fontSize="17">INSTITUTE OF</text><text className="lbl" x="1483" y="327" fontSize="17">SCIENCE &amp;</text><text className="lbl" x="1483" y="349" fontSize="17">TECHNOLOGY</text>
<g id="UNK-C1" className={cn('b com', selectedId === 'UNK-C1' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'UNK-C1'} onClick={() => choose('UNK-C1')} onKeyDown={(e) => onRegionKey(e, 'UNK-C1')} data-id="UNK-C1" data-name="Unlabeled" data-unlabeled="true" data-zone="commons"><rect x="1358" y="245" width="38" height="20"/></g>
<g id="WORKSHOP" className={cn('b com', selectedId === 'WORKSHOP' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'WORKSHOP'} onClick={() => choose('WORKSHOP')} onKeyDown={(e) => onRegionKey(e, 'WORKSHOP')} data-id="WORKSHOP" data-name="Workshop" data-zone="commons"><polygon points="1360,112 1455,108 1487,150 1485,178 1358,160"/><text className="lbl" x="1423" y="158" fontSize="17">WORKSHOP</text></g>
<g id="BLK-3" className={cn('b com', selectedId === 'BLK-3' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-3'} onClick={() => choose('BLK-3')} onKeyDown={(e) => onRegionKey(e, 'BLK-3')} data-id="BLK-3" data-name="Block 3" data-map-no="3" data-zone="commons"><rect x="1246" y="706" width="66" height="132"/><text className="lbl" x="1279" y="773" fontSize="18">BLOCK</text><text className="lbl" x="1279" y="797" fontSize="24">3</text></g>
<g id="BLK-23N" className={cn('b com', selectedId === 'BLK-23N' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-23N'} onClick={() => choose('BLK-23N')} onKeyDown={(e) => onRegionKey(e, 'BLK-23N')} data-id="BLK-23N" data-name="Block 23 (north)" data-map-no="23" data-zone="commons"><polygon points="230,553 284,553 284,613 262,613 258,640 252,613 230,613"/><text className="lbl" x="257" y="590" fontSize="24">23</text></g>
<text className="lbl" x="147" y="566" fontSize="16">OM VINAYAGA</text><text className="lbl" x="147" y="588" fontSize="16">HOSTEL</text>
<g id="BLK-23S" className={cn('b com', selectedId === 'BLK-23S' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'BLK-23S'} onClick={() => choose('BLK-23S')} onKeyDown={(e) => onRegionKey(e, 'BLK-23S')} data-id="BLK-23S" data-name="Block 23 (strip)" data-map-no="23" data-zone="commons"><rect x="118" y="622" width="110" height="25"/><text className="lbl" x="172" y="642" fontSize="22">23</text></g>

{/*  GREENERY & SPORTS  */}
<g id="LAWN" className={cn('b grn', selectedId === 'LAWN' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'LAWN'} onClick={() => choose('LAWN')} onKeyDown={(e) => onRegionKey(e, 'LAWN')} data-id="LAWN" data-name="Lawn" data-zone="greenery"><polygon points="908,145 1150,145 1148,318 1125,320 1040,300 908,300"/><text className="lbl" x="1023" y="230" fontSize="17">LAWN</text></g>
<g id="EEC-COURT" className={cn('b grn', selectedId === 'EEC-COURT' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'EEC-COURT'} onClick={() => choose('EEC-COURT')} onKeyDown={(e) => onRegionKey(e, 'EEC-COURT')} data-id="EEC-COURT" data-name="EEC Courtyard" data-map-no="19" data-zone="greenery"><polygon points="378,498 440,498 440,520 425,520 425,545 440,545 440,570 378,570"/><text className="lbl" x="394" y="552" fontSize="24">19</text></g>
<g id="OAT" className={cn('b grn', selectedId === 'OAT' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'OAT'} onClick={() => choose('OAT')} onKeyDown={(e) => onRegionKey(e, 'OAT')} data-id="OAT" data-name="Open Air Theatre (OAT)" data-zone="greenery"><polygon points="465,718 500,685 560,665 620,663 680,676 680,820 692,836 600,810 540,795 500,785 470,750"/><text className="lbl" x="555" y="767" fontSize="17">OAT</text></g>
<path className="arc" d="M490,778 C490,720 540,690 600,690 C640,690 665,705 668,720"/>
<path className="arc" d="M505,775 C505,730 548,706 600,706 C632,706 650,716 652,728"/>
<g id="SPORTS" className={cn('b grn', selectedId === 'SPORTS' && 'selected')} role="button" tabIndex={0} aria-pressed={selectedId === 'SPORTS'} onClick={() => choose('SPORTS')} onKeyDown={(e) => onRegionKey(e, 'SPORTS')} data-id="SPORTS" data-name="EEC Playground / Sports Complex" data-zone="greenery"><polygon points="1487,430 1600,430 1600,940 1487,940"/><text className="lbl" x="1548" y="690" fontSize="18" transform="rotate(-90 1548 690)">EEC PLAYGROUND / SPORTS COMPLEX</text></g>

{/*  ROAD, PARKING & GATE LABELS  */}
<g id="road-labels">
<text className="rl" x="1090" y="130" fontSize="22" transform="rotate(-5 1090 130)">SRM BMS BLOCK ROAD</text>
<text className="rl" x="1340" y="250" fontSize="18" transform="rotate(-85 1340 250)">SRM BMS BLOCK ROAD</text>
<text className="rl" x="715" y="1005" fontSize="26" transform="rotate(10 715 1005)">BHARATHI SALAI</text>
<text className="rl" x="685" y="650" fontSize="20">PARKING</text>
<text className="rl" x="837" y="485" fontSize="19">PARKING</text>
<text className="rl" x="865" y="788" fontSize="19" transform="rotate(-90 865 788)">PARKING</text>
<text className="rl" x="988" y="947" fontSize="19">PARKING</text>
<text className="rl" x="415" y="1100" fontSize="24">CAMPUS</text><text className="rl" x="415" y="1128" fontSize="24">GATE</text>
<text className="rl" x="1239" y="1109" fontSize="24">MAIN</text><text className="rl" x="1239" y="1137" fontSize="24">GATE</text>
<text className="rl" x="943" y="1082" fontSize="21">#24</text>
<text className="rl" x="1098" y="1082" fontSize="21">R11 RAYALA NAGAR</text><text className="rl" x="1098" y="1106" fontSize="21">POLICE STATION</text>
</g>

{/*  LEGEND  */}
<g id="legend">
<rect x="185" y="38" width="320" height="248" className="fill-map-bg" opacity=".92"/>
<text x="190" y="72" fontSize="28" fontWeight="700" className="fill-map-ink">MAP LEGEND</text>
<rect x="190" y="90" width="44" height="20" className="fill-map-eng"/><text x="246" y="108" fontSize="20" fontWeight="700" className="fill-map-ink">ENGINEERING CAMPUS</text>
<rect x="190" y="123" width="44" height="20" className="fill-map-med"/><text x="246" y="141" fontSize="20" fontWeight="700" className="fill-map-ink">MEDICAL CAMPUS &amp; DENTAL</text>
<rect x="190" y="156" width="44" height="20" className="fill-map-host"/><text x="246" y="174" fontSize="20" fontWeight="700" className="fill-map-ink">HOSTELS</text>
<rect x="190" y="189" width="44" height="20" className="fill-map-com"/><text x="246" y="207" fontSize="20" fontWeight="700" className="fill-map-ink">COMMONS &amp; UTILITIES</text>
<rect x="190" y="222" width="44" height="20" className="fill-map-grn"/><text x="246" y="240" fontSize="20" fontWeight="700" className="fill-map-ink">GREENERY &amp; SPORTS</text>
<rect x="190" y="255" width="44" height="20" className="fill-map-road"/><text x="246" y="273" fontSize="20" fontWeight="700" className="fill-map-ink">ROADS &amp; PARKING</text>
</g>

{/*  COMPASS  */}
<g id="compass">
<circle cx="72" cy="102" r="33" className="fill-map-bg stroke-map-ink" strokeWidth="3"/>
<polygon points="72,78 62,112 72,106 82,112" className="fill-map-ink"/>
<text x="72" y="64" fontSize="26" fontWeight="700" textAnchor="middle" className="fill-map-ink">N</text>
</g>

{/*  SCALE BAR  */}
<g id="scale-bar">
<rect x="1360" y="1148" width="55" height="9" className="fill-map-dark"/><rect x="1415" y="1148" width="55" height="9" className="fill-map-light stroke-map-dark"/>
<rect x="1470" y="1148" width="55" height="9" className="fill-map-dark"/><rect x="1525" y="1148" width="55" height="9" className="fill-map-light stroke-map-dark"/>
<text x="1470" y="1182" fontSize="16" fontWeight="700" textAnchor="middle" className="fill-map-ink">Scale Bar</text>
</g>

{/*  EMPTY LAYER FOR REACT OVERLAYS: incidents, work orders, closures  */}

          {/* REACT OVERLAYS: Incidents, closures, and status badges */}
          <g id="overlays" pointerEvents="none">
            {resolvedOverlays.map(({ id, overlay, pos }) => {
              const hasBadge = typeof overlay.badge === 'number' && overlay.badge > 0
              const hasStatus = overlay.state && overlay.state !== 'OPEN'
              return (
                <g key={id} transform={`translate(${pos.x} ${pos.y})`}>
                  {hasStatus ? (
                    <g transform="translate(-18, -18)">
                      <circle cx="18" cy="18" r="16" className="fill-surface stroke-ink" strokeWidth={2} />
                      <text x="18" y="24" fontSize={18} fontWeight={700} textAnchor="middle" className="fill-ink">
                        {STATE_GLYPH[overlay.state]}
                      </text>
                    </g>
                  ) : null}
                  {hasBadge ? (
                    <g transform="translate(10, -18)">
                      <circle cx="14" cy="14" r="14" className="fill-danger" />
                      <text x="14" y="20" fontSize={15} fontWeight={700} textAnchor="middle" className="fill-accent-contrast">
                        {overlay.badge}
                      </text>
                    </g>
                  ) : null}
                </g>
              )
            })}

            {markers.map((marker) => (
              <g key={marker.id} transform={`translate(${marker.x} ${marker.y})`}>
                <title>{marker.label}</title>
                <circle cx="0" cy="0" r="11" className={cn(MARKER_FILL[marker.tone], 'stroke-surface')} strokeWidth={3} />
              </g>
            ))}
            </g>
            </>
          )}
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

export function MapLegend({ states = ['OPEN', 'AFFECTED', 'CLOSED', 'MAINTENANCE'] as RegionState[] }: { states?: RegionState[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted" aria-label="Map legend">
      {states.map((state) => (
        <li key={state} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className={cn('grid size-5 place-items-center rounded-sm border text-[0.625rem] font-bold text-ink', REGION_CLASS[state].replace('fill-', 'bg-').replace('stroke-', 'border-'))}
          >
            {STATE_GLYPH[state]}
          </span>
          {STATE_TEXT[state]}
        </li>
      ))}
    </ul>
  )
}
