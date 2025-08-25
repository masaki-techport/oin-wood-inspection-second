/**
 * Type declarations for extended File objects
 */

// Extend the File interface to include webkitRelativePath
interface FileWithPath extends File {
  /**
   * The relative path of the file when selected using webkitdirectory
   * This property is available when files are selected using a directory input
   */
  webkitRelativePath: string;
}