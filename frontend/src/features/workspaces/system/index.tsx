import type { ComponentType } from 'react'
import { RolesScreen } from '@/features/admin/RolesScreen'
import { UsersScreen } from '@/features/admin/UsersScreen'
import {
  CampusDataScreen,
  IntegrationsScreen,
  InventoryMasterScreen,
  RulesScreen,
  SeedScreen,
  SlaPoliciesScreen,
  StaffScreen,
  SystemOverviewScreen,
} from '@/features/admin/AdminScreens'
import { AuditScreen } from '@/features/audit/AuditScreen'

/** System Administrator workspace: configuration only. It never grants business approval. */
export const screens: Record<string, ComponentType> = {
  'sys.overview': SystemOverviewScreen,
  'sys.users': UsersScreen,
  'sys.roles': RolesScreen,
  'sys.campus': CampusDataScreen,
  'sys.staff': StaffScreen,
  'sys.inventoryMaster': InventoryMasterScreen,
  'sys.rules': RulesScreen,
  'sys.slaPolicy': SlaPoliciesScreen,
  'sys.integrations': IntegrationsScreen,
  'sys.audit': () => <AuditScreen title="Audit Logs" description="Configuration and account changes across the whole system." />,
  'sys.seed': SeedScreen,
}
