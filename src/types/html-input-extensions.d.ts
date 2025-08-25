// Type declarations for non-standard HTML input attributes
interface HTMLInputElement {
  // Directory selection attributes for folder input
  webkitdirectory?: string | boolean;
  directory?: string | boolean;
  
  // For accessing the webkitRelativePath property on File objects
  files?: FileList & {
    item(index: number): File & { webkitRelativePath: string };
  };
}