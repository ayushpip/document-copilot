type Env = {
  apiBaseUrl: string
  supabaseUrl: string
  supabaseAnonKey: string
}

function requireEnv(name: string): string {
  const value = import.meta.env[name]

  if (typeof value !== 'string' || value.trim() === '') {
    throw new Error(`Missing required environment variable: ${name}`)
  }

  return value.trim()
}

function requireUrl(name: string): string {
  const value = requireEnv(name)

  try {
    return new URL(value).toString().replace(/\/$/, '')
  } catch {
    throw new Error(`Invalid URL in environment variable: ${name}`)
  }
}

export const env: Env = {
  apiBaseUrl: requireUrl('VITE_API_BASE_URL'),
  supabaseUrl: requireUrl('VITE_SUPABASE_URL'),
  supabaseAnonKey: requireEnv('VITE_SUPABASE_ANON_KEY'),
}
