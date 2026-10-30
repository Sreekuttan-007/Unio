import type { ComponentType } from 'react'
import { AcademicImpactScreen, BookRoomScreen, MyBookingsScreen } from '@/features/bookings/BookingScreens'
import { CampusMapScreen } from '@/features/campus/CampusMapScreen'
import { FacultyHome } from '@/features/dashboard/HomeScreens'
import { ReportIssueScreen } from '@/features/issues/ReportIssueScreen'

/** Faculty workspace: report, book and see what affects your sessions. */
export const screens: Record<string, ComponentType> = {
  'faculty.home': FacultyHome,
  'faculty.report': () => <ReportIssueScreen academicImpact />,
  'faculty.booking': BookRoomScreen,
  'faculty.myBookings': () => <MyBookingsScreen />,
  'faculty.impact': AcademicImpactScreen,
  'faculty.map': () => <CampusMapScreen title="Campus Map" description="Find rooms and see which buildings are affected." />,
}
