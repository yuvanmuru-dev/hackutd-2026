import { readFileSync } from 'node:fs';
import { Ajv2020 } from 'ajv/dist/2020.js';
import formatsModule from 'ajv-formats';

const schema = JSON.parse(readFileSync(new URL('../../contracts/schema.json', import.meta.url), 'utf8'));
const ajv = new Ajv2020({ strict: false, allErrors: true });
formatsModule.default(ajv);
ajv.addSchema(schema, 'titan');
const validators = new Map<string, ReturnType<typeof ajv.compile>>();
export function valid(type: string, value: unknown): boolean {
  let validator = validators.get(type);
  if (!validator) { validator = ajv.compile({ $ref: `titan#/$defs/${type}` }); validators.set(type, validator); }
  return !!validator(value);
}

export function safeOutbound(text: string): boolean {
  text = text.normalize('NFKC').replace(/[\u200B-\u200D\uFEFF]/g, '').replace(/[\u2018\u2019]/g, "'");
  // Block explicit URLs, bare domains, IP links, email links and obfuscated schemes.
  if (/(?:https?\s*:|www\s*\.|\b[a-z][a-z0-9+.-]*:\/\/|\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[\p{L}\d][\p{L}\d-]*(?:\.[\p{L}\d-]+)*\.[\p{L}]{2,}\b)/iu.test(text)) return false;
  // Allow warnings such as "never share your PIN" and approval to reset a PIN.
  const clauses = text.split(/[.!?;\n]|\bbut\b/i);
  return !clauses.some(clause => {
    if (/^\s*(?:we|titan)\s+(?:will\s+)?never ask\b/i.test(clause) && !/\b(?:then|also|and (?:send|share|tell|give|read|enter|type|reply|provide|confirm))\b/i.test(clause)) return false;
    // Incident summaries describe the scammer's past request. Remove only that
    // bounded reported span, then check remaining text for a live request.
    clause = clause.replace(/\b(?:someone|(?:a|the)\s+(?:caller|scammer|person)|they|he|she)\b[^,;\n]{0,80}?\b(?:asked|told|pressured|convinced|instructed)\s+you\s+to\s+[^,;\n]{0,120}?\b(?:pin|password|passcode|code)\b/gi, '');
    clause = clause.replace(/\bnever\s+ask\s+you\s+to\s+[^,;\n]{0,120}?\b(?:pin|password|passcode|code)\b/gi, '');
    clause = clause.replace(/\b(?:never|don't|do not)\s+(?:send|share|tell|give|read|enter|type|provide|disclose)\b[^,]*\b(?:pin|password|passcode|code)\b/gi, '');
    return /\b(?:send|share|tell|give|read|enter|type|reply|provide|confirm)\b.{0,55}\b(?:pin|password|passcode|code)\b/i.test(clause)
      || /\bwhat(?:'s| is)\b.{0,25}\b(?:pin|password|passcode|code)\b/i.test(clause);
  });
}
