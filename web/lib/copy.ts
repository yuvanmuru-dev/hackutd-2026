/** T-Mobile's product names are proper nouns: fix their case in any text we display, the brain's included. */
export function productCase(text: string): string {
  return text
    .replace(/\bport[ -]out protection\b/gi, "Port Out Protection")
    .replace(/\bsim protection\b/gi, "SIM Protection")
    .replace(/\bscam block\b/gi, "Scam Block")
    .replace(/\btransfer pin(s?)\b/gi, "Transfer PIN$1")
    .replace(/\baccount takeover protection\b/gi, "Account Takeover Protection");
}
