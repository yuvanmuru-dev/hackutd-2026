import { ApiError } from '@photon-ai/api';
import { BrainError } from './brain.js';
import { DeliveryError } from './photon.js';

// Never print exception bodies: providers and validators can include private input.
export function errorFields(error: unknown) {
  if (error instanceof ApiError) return { category: 'photon_api', status: error.status, requestId: error.requestId };
  if (error instanceof BrainError) return { category: 'brain_api', status: error.status };
  if (error instanceof DeliveryError) return { category: 'delivery', code: error.code };
  const codes = new Set(['invalid_photon_event', 'project_mismatch', 'invalid_message_id',
    'unsupported_inbound_content', 'inbound_text_too_large', 'case_owner_mismatch', 'invalid_brain_event',
    'image_too_large', 'unsupported_image_type', 'attachment_project_mismatch']);
  if (error instanceof Error && codes.has(error.message)) return { category: 'validation', code: error.message };
  return { category: 'internal' };
}
