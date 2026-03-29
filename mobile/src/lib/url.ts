export function getUrlOrigin(value: string): string {
  const trimmed = value.trim();
  const match = trimmed.match(/^(https?:\/\/[^/]+)/i);
  if (!match) {
    throw new Error("유효한 URL이 아닙니다.");
  }
  return match[1];
}
