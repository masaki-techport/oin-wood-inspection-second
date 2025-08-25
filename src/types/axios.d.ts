import 'axios';

declare module 'axios' {
  export interface AxiosRequestConfig {
    suppressGlobalError?: boolean;
  }
}