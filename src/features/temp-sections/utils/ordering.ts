import { TempSection } from '../../../types/temp-sections';

/**
 * Convert an Excel-style column label (A..Z, AA, AB, ...) to its 1-based numeric value.
 * Example: A -> 1, Z -> 26, AA -> 27, AB -> 28, BA -> 53, AAA -> 703
 */
function labelToNumber(label: string): number {
  if (!label) return 0;
  let value = 0;
  for (let i = 0; i < label.length; i++) {
    const code = label.charCodeAt(i);
    // Only accept uppercase A-Z; fallback safely otherwise
    if (code < 65 || code > 90) {
      // Normalize to uppercase and retry once for robustness
      const upper = label.toUpperCase();
      if (upper !== label) {
        return labelToNumber(upper);
      }
      return 0;
    }
    value = value * 26 + (code - 64);
  }
  return value;
}

/**
 * Sort sections by true Excel-style order: A, B, ..., Z, AA, AB, ...
 */
export function sortSectionsAlphabetically(sections: TempSection[]): TempSection[] {
  if (!sections || sections.length === 0) return [];
  return [...sections].sort((a, b) => labelToNumber(a.label || '') - labelToNumber(b.label || ''));
}

// Exported for testing convenience
export const __test__ = { labelToNumber };

