import type { ComponentType } from 'react'
import { CampusMapScreen } from '@/features/campus/CampusMapScreen'
import { AvailabilityScreen, MaintenanceHistoryScreen, MyPartsScreen, MyTasksScreen } from '@/features/workorders/TechnicianScreens'

/** Technician workspace. Designed for a phone held in one hand. */
export const screens: Record<string, ComponentType> = {
  'tech.tasks': MyTasksScreen,
  'tech.parts': MyPartsScreen,
  'tech.availability': AvailabilityScreen,
  'tech.history': MaintenanceHistoryScreen,
  'tech.map': () => <CampusMapScreen title="Site Map" description="Where your work is. Aryabhata Block is selected for your open tasks." initialSelected="bld-arb" />,
}
