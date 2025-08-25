import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import moment from 'moment';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function dateToString(date: Date, format = 'yyyy/MM/DD HH:mm:ss') {
  return moment(date).format(format);
}

export function truncateWithEllipsis(str: string, maxLength = 80) {
  if (str.length > maxLength) {
    return str.substring(0, maxLength - 3) + '...';
  }
  return str;
}
