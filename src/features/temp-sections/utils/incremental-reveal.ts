import { TempSection } from '../../../types/temp-sections';

/**
 * Return sections that are present in incoming but not in existing, sorted FIFO.
 */
export function diffNewSections(
  existing: TempSection[],
  incoming: TempSection[]
): TempSection[] {
  if (!existing || !incoming) return [];
  
  const existingIds = new Set(existing.map(s => s.id));
  const newOnes = incoming.filter(s => s && s.id && !existingIds.has(s.id));
  
  // Sort by label for alphabetical order (A, B, C, D, E, F...)
  const sorted = newOnes.sort((a, b) => (a.label || '').localeCompare(b.label || ''));
  
  console.log(`🔍 diffNewSections: existing=${existing.length}, incoming=${incoming.length}, new=${sorted.length}`);
  if (sorted.length > 0) {
    console.log(`📝 New sections: ${sorted.map(s => `${s.label}(${s.id})`).join(', ')}`);
  }
  
  return sorted;
}

/**
 * Small queue to reveal sections one-by-one.
 */
export class IncrementalRevealQueue {
  private queue: TempSection[] = [];
  private queuedIds = new Set<string>();

  enqueue(items: TempSection[]) {
    if (!items || items.length === 0) return;
    
    // Only enqueue items that haven't been queued before
    const newItems = items.filter(item => item && item.id && !this.queuedIds.has(item.id));
    
    if (newItems.length > 0) {
      // Sort by label for alphabetical order before adding to queue
      const sortedItems = newItems.sort((a, b) => (a.label || '').localeCompare(b.label || ''));
      this.queue.push(...sortedItems);
      sortedItems.forEach(item => this.queuedIds.add(item.id));
      console.log(`📥 Enqueued ${sortedItems.length} new sections: ${sortedItems.map(s => s.label).join(', ')}`);
    }
  }

  dequeue(): TempSection | null {
    if (this.queue.length === 0) return null;
    const item = this.queue.shift() ?? null;
    if (item) {
      this.queuedIds.delete(item.id);
      console.log(`📤 Dequeued section: ${item.label}(${item.id})`);
    }
    return item;
  }

  clear() {
    this.queue = [];
    this.queuedIds.clear();
  }

  get size() {
    return this.queue.length;
  }
}


