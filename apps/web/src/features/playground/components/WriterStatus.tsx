export function ErrorText({ error }: { error: unknown }) {
  return error ? <p role="alert" className="notice">{error instanceof Error ? error.message : String(error)}</p> : null;
}
