import type { ComponentType } from 'react'
import { CampusMapScreen } from '@/features/campus/CampusMapScreen'
import { StudentHome } from '@/features/dashboard/HomeScreens'
import { ReportIssueScreen } from '@/features/issues/ReportIssueScreen'
import { MyReportsScreen } from '@/features/issues/MyReportsScreen'
import { NoticesScreen } from '@/features/issues/NoticesScreen'

/** Student workspace: report and track. Screen titles match the navigation labels from the server. */
export const screens: Record<string, ComponentType> = {
  'student.home': StudentHome,
  'student.report': () => <ReportIssueScreen />,
  'student.myReports': MyReportsScreen,
  'student.notices': NoticesScreen,
  'student.map': () => <CampusMapScreen title="Campus Map" description="Which buildings are open, closed or affected right now." />,
}
