import type { components } from '@/types/api.generated'

/** Named aliases over the generated schema, so a backend change surfaces here as a type error. */
type Schemas = components['schemas']

export type BootstrapResponse = Schemas['BootstrapResponse']
export type NavItem = Schemas['NavItem']
export type DemoAccount = Schemas['DemoAccount']
export type TokenResponse = Schemas['TokenResponse']
export type UserDto = Schemas['UserDto']
export type RoleDto = Schemas['RoleDto']
export type AuditEntry = Schemas['AuditEntry']
export type CreateUserBody = Schemas['CreateUser']
export type UserPage = Schemas['PageResponse_UserDto_']
export type AuditPage = Schemas['PageResponse_AuditEntry_']
