export type LoggingProgressBarProps = {
  progress: number // scale is 0 to 1
  logs?: string[]
  filename?: string
  status?: 'processing' | 'error' | 'done'
}

export default function LoggingProgressBar({ progress, logs = [], filename, status = 'processing' }: LoggingProgressBarProps) {
  // Clamp progress between 0 and 1
  const pct = Math.max(0, Math.min(1, progress)) * 100
  const lastLog = logs.length > 0 ? logs[logs.length - 1] : ''

  return (
    <div className={`flex w-full flex-col gap-2`}>
      <div className="h-5 w-full overflow-hidden rounded bg-gray-200" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} style={{ position: 'relative' }}>
        <div
          className="h-full transition-all duration-200"
          style={{
            width: `${pct}%`,
            backgroundColor: status === 'done' ? '#22de22' : '#EF4444',
            position: 'relative',
            backgroundImage: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.18) 0, rgba(255,255,255,0.18) 6px, transparent 6px, transparent 12px)',
            backgroundSize: '17px 17px',
            backgroundPosition: '0 0',
            animation: status === 'processing' ? 'progress-stripes-move 0.75s linear infinite' : undefined,
          }}
        />
      </div>
      <div className="w-full space-y-1">
        {filename && (
          <div className="text-pale-black truncate text-xs font-semibold" title={filename}>
            {filename}
          </div>
        )}
        <div className={`text-sm ${status === 'error' ? 'text-red font-medium' : 'text-black'}`}>{lastLog || (status === 'processing' ? 'Обработка...' : '')}</div>
      </div>
    </div>
  )
}
