import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/platform/auth/AuthProvider'

/** Go to a screen by its navigation key. A key the role does not have simply returns no path. */
export function useNavTo() {
  const navigate = useNavigate()
  const { bootstrap } = useAuth()
  const pathOf = (key: string) => bootstrap?.navigation.find((item) => item.key === key)?.path ?? null
  return {
    pathOf,
    go: (key: string) => {
      const path = pathOf(key)
      if (path) navigate(path)
    },
  }
}
