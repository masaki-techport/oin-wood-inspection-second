// Centralized helpers for working with inspection image paths and URLs
// Keep logic in one place to avoid duplication and drift between components

type ImageUrlOptions = {
  quality?: 'low' | 'medium' | 'high';
  size?: 'thumbnail' | 'medium' | 'full';
  progressive?: boolean;
};

const imageUrlCache: Record<string, string> = {};
const MAX_CACHE_SIZE = 1000;

/**
 * Extract `inspection/<folder>` relative path expected by backend `/inspections/all`.
 * Returns null if it cannot be determined.
 */
export function extractInspectionFolderRelativePath(fullPath: string): string | null {
  if (!fullPath) return null;

  try {
    const normalized = fullPath.replace(/\\/g, '/');

    // 0) If an absolute path is provided (Windows or Unix), return its directory as-is
    // Windows: C:/...  |  Unix: /...
    const isWindowsAbs = /^[a-zA-Z]:\//.test(normalized);
    const isUnixAbs = normalized.startsWith('/');
    if (isWindowsAbs || isUnixAbs) {
      // If a filename is included, strip it and return folder
      const hasExtension = /\.[a-zA-Z0-9]+$/.test(normalized);
      if (hasExtension) {
        const lastSlash = normalized.lastIndexOf('/');
        if (lastSlash > 0) return normalized.substring(0, lastSlash);
      }
      return normalized;
    }

    // Prefer explicit "/inspection/<folder>" at path end
    const folderMatch = normalized.match(/\/inspection\/([^/]+)$/);
    if (folderMatch && folderMatch[1]) {
      return `inspection/${folderMatch[1]}`;
    }

    // Fallback: any occurrence of "/inspection/<folder>"
    const anyMatch = normalized.match(/\/inspection\/([^/]+)/);
    if (anyMatch && anyMatch[1]) {
      return `inspection/${anyMatch[1]}`;
    }

    // Last resort: look for trailing date-like token 20250101_123456
    const dateLike = normalized.match(/(\d{8}_\d{4,6})$/);
    if (dateLike && dateLike[1]) {
      return `inspection/${dateLike[1]}`;
    }

    // If path already starts with inspection/, keep it
    if (/^inspection\//i.test(normalized)) {
      return normalized;
    }

    return null;
  } catch {
    return null;
  }
}

/** Build optimized API file URL for an image path with inspection id. */
export function buildApiFileUrl(imagePath: string, inspectionId: number, options: ImageUrlOptions = {}): string {
  if (!imagePath) return '';

  const { quality = 'medium', size = 'full', progressive = false } = options;
  const cacheKey = `${imagePath}:${inspectionId}:${quality}:${size}:${progressive}`;
  if (imageUrlCache[cacheKey]) return imageUrlCache[cacheKey];

  const apiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;

  // Normalize and clean duplicated segments like inspection/.../inspection/
  let path = imagePath.replace(/\\/g, '/');
  const duplicate = path.match(/inspection\/.*?inspection\//i);
  if (duplicate) {
    const idx = path.toLowerCase().lastIndexOf('inspection/');
    if (idx !== -1) path = `src-api/data/images/${path.substring(idx)}`;
  } else {
    const afterInspection = path.match(/inspection\/(.*?)$/i);
    if (afterInspection && afterInspection[1]) {
      path = `src-api/data/images/inspection/${afterInspection[1]}`;
    }
  }

  const params = new URLSearchParams();
  if (imagePath.toLowerCase().endsWith('.bmp')) params.append('convert', 'jpg');
  if (quality === 'low') params.append('quality', '60');
  else if (quality === 'medium') params.append('quality', '85');
  else if (quality === 'high') params.append('quality', '95');

  if (size === 'thumbnail') params.append('size', '150x150');
  else if (size === 'medium') params.append('size', '500x500');
  if (progressive) params.append('progressive', 'true');

  const base = `${apiBaseUrl}/api/file?path=${encodeURIComponent(path)}&inspection_id=${inspectionId}`;
  const finalUrl = params.toString() ? `${base}&${params.toString()}` : base;

  if (Object.keys(imageUrlCache).length >= MAX_CACHE_SIZE) {
    // Remove roughly 20% oldest keys
    const keys = Object.keys(imageUrlCache);
    for (let i = 0; i < Math.floor(keys.length * 0.2); i++) delete imageUrlCache[keys[i]];
  }
  imageUrlCache[cacheKey] = finalUrl;
  return finalUrl;
}

/** Extract image number from a path using the last occurrence of "No_####". */
export function extractImageNoFromPath(imagePath: string): number | null {
  if (!imagePath) return null;
  try {
    const matches = imagePath.match(/No_(\d+)/g);
    if (matches && matches.length > 0) {
      const last = matches[matches.length - 1];
      const num = parseInt(last.replace('No_', ''), 10);
      return isNaN(num) ? null : num;
    }
    return null;
  } catch {
    return null;
  }
}


