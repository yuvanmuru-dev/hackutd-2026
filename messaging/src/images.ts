export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export interface InboundContent { text: string; attachments: string[]; }

export function inboundContent(value: unknown): InboundContent {
  if (!value || typeof value !== 'object') throw new Error('unsupported_inbound_content');
  const content = value as { type?: string; parts?: unknown[] };
  const parts = content.type === 'group' && Array.isArray(content.parts) ? content.parts : [value];
  const texts: string[] = [], attachments: string[] = [];
  for (const value of parts) {
    if (!value || typeof value !== 'object') throw new Error('unsupported_inbound_content');
    const part = value as { type?: string; format?: string; text?: string; attachmentId?: string };
    if (part.type === 'text' && part.format === 'plain' && typeof part.text === 'string') texts.push(part.text);
    else if (part.type === 'attachment' && typeof part.attachmentId === 'string' && part.attachmentId) attachments.push(part.attachmentId);
    else throw new Error('unsupported_inbound_content');
  }
  const text = texts.join('\n');
  if (Buffer.byteLength(text, 'utf8') > 4096) throw new Error('inbound_text_too_large');
  if (!text && !attachments.length) throw new Error('unsupported_inbound_content');
  return { text, attachments };
}

export function imageDataUrl(contentType: string, bytes: Uint8Array): string {
  if (bytes.byteLength > MAX_IMAGE_BYTES) throw new Error('image_too_large');
  const buffer = Buffer.from(bytes);
  const png = buffer.length >= 8 && buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  const jpeg = buffer.length >= 3 && buffer[0] === 255 && buffer[1] === 216 && buffer[2] === 255;
  if (!((contentType === 'image/png' && png) || (contentType === 'image/jpeg' && jpeg))) throw new Error('unsupported_image_type');
  return `data:${contentType};base64,${buffer.toString('base64')}`;
}
