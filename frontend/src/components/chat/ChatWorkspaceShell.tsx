import type { ReactNode } from 'react'

type ChatWorkspaceShellProps = {
  isSidebarCollapsed: boolean
  isSourcePanelOpen: boolean
  sidebar: ReactNode
  children: ReactNode
  sourcePanel: ReactNode
}

export function ChatWorkspaceShell({
  isSidebarCollapsed,
  isSourcePanelOpen,
  sidebar,
  children,
  sourcePanel,
}: ChatWorkspaceShellProps) {
  const gridTemplateColumns = `${isSidebarCollapsed ? '72px' : '280px'} minmax(0, 1fr) ${
    isSourcePanelOpen ? 'minmax(320px, 380px)' : '0px'
  }`

  return (
    <main className="grid h-svh bg-background text-foreground transition-[grid-template-columns]" style={{ gridTemplateColumns }}>
      {sidebar}
      {children}
      {sourcePanel}
    </main>
  )
}
