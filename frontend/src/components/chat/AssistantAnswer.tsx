type AssistantAnswerProps = {
  content: string
}

function splitTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isDividerRow(line: string) {
  return /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim())
}

function isTableStart(lines: string[], index: number) {
  return lines[index]?.trim().startsWith('|') && lines[index + 1] && isDividerRow(lines[index + 1])
}

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={`${part}-${index}`} className="rounded bg-muted px-1 py-0.5 text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      )
    }
    return <span key={`${part}-${index}`}>{part}</span>
  })
}

export function AssistantAnswer({ content }: AssistantAnswerProps) {
  const lines = content.split('\n')
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    if (isTableStart(lines, index)) {
      const tableLines = [lines[index]]
      index += 2
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        tableLines.push(lines[index])
        index += 1
      }
      const [headerLine, ...bodyLines] = tableLines
      const headers = splitTableRow(headerLine)
      blocks.push(
        <div key={`table-${index}`} className="overflow-x-auto rounded-md border border-border">
          <table className="min-w-full border-collapse text-sm">
            <thead className="bg-muted/60">
              <tr>
                {headers.map((header) => (
                  <th key={header} className="border-b border-border px-3 py-2 text-left font-medium">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyLines.map((rowLine) => (
                <tr key={rowLine} className="border-t border-border/70">
                  {splitTableRow(rowLine).map((cell, cellIndex) => (
                    <td key={`${rowLine}-${cellIndex}`} className="px-3 py-2 align-top text-muted-foreground">
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }

    if (trimmed.startsWith('### ')) {
      blocks.push(
        <h3 key={`${trimmed}-${index}`} className="!m-0 pt-2 text-base font-semibold text-foreground">
          {renderInline(trimmed.slice(4))}
        </h3>,
      )
    } else if (trimmed.startsWith('## ')) {
      blocks.push(
        <h2 key={`${trimmed}-${index}`} className="!m-0 pt-2 text-lg font-semibold text-foreground">
          {renderInline(trimmed.slice(3))}
        </h2>,
      )
    } else if (trimmed.startsWith('- ')) {
      const items = []
      while (index < lines.length && lines[index].trim().startsWith('- ')) {
        items.push(lines[index].trim().slice(2))
        index += 1
      }
      blocks.push(
        <ul key={`list-${index}`} className="list-disc space-y-1 pl-5">
          {items.map((item) => (
            <li key={item}>{renderInline(item)}</li>
          ))}
        </ul>,
      )
      continue
    } else {
      blocks.push(
        <p key={`${trimmed}-${index}`} className="whitespace-pre-wrap">
          {renderInline(trimmed)}
        </p>,
      )
    }
    index += 1
  }

  return <div className="space-y-3">{blocks}</div>
}
