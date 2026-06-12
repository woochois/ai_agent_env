import { Environment, Network, RecordSource, Store, RequestParameters, Variables } from 'relay-runtime'

const TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const GRAPHQL_URL = '/graphql'

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const handleAuthError = async (): Promise<boolean> => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refreshToken) return false

  try {
    const response = await fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken }),
    })

    if (!response.ok) return false

    const data = await response.json()
    localStorage.setItem(TOKEN_KEY, data.accessToken)
    localStorage.setItem(REFRESH_TOKEN_KEY, data.refreshToken)
    return true
  } catch {
    return false
  }
}

const graphqlFetch = async (operation: RequestParameters, variables: Variables) => {
  const response = await fetch(GRAPHQL_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ query: operation.text, variables }),
  })

  if (response.status === 401) {
    const refreshed = await handleAuthError()
    if (!refreshed) {
      // Clear tokens and redirect to login
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      window.location.href = '/login'
      throw new Error('Authentication failed')
    }
    // Retry with new token
    return graphqlFetch(operation, variables)
  }

  return response.json()
}

export const createRelayEnvironment = () =>
  new Environment({
    network: Network.create(graphqlFetch),
    store: new Store(new RecordSource()),
  })

export let relayEnvironment = createRelayEnvironment()

export const resetRelayEnvironment = () => {
  relayEnvironment = createRelayEnvironment()
  return relayEnvironment
}
