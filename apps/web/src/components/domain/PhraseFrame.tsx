import { cn } from "@/lib/utils"

type PhraseFrameProps = {
  frame: string
  values?: Record<string, string>
  className?: string
}

function PhraseFrame({ frame, values = {}, className }: PhraseFrameProps) {
  const parts = frame.split(/(\{[^}]+\})/g)

  return (
    <span className={cn("font-serif text-lg leading-relaxed", className)}>
      {parts.map((part, index) => {
        const match = part.match(/^\{([^}]+)\}$/)
        if (!match) return <span key={`${part}-${index}`}>{part}</span>

        const name = match[1]
        const value = values[name]?.trim()
        return (
          <mark
            key={`${name}-${index}`}
            role="img"
            className="rounded-[2px] bg-[var(--slot-bg)] px-1 text-[var(--slot)]"
            aria-label={value ? `${name} slot: ${value}` : `[${name}]`}
          >
            {value || `[${name}]`}
          </mark>
        )
      })}
    </span>
  )
}

export { PhraseFrame }
