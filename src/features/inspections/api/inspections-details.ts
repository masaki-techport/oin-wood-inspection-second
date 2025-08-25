import { api } from '@/lib/api-client';
import { ApiResult, Inspection, InspectionResult, InspectionDetailsImg } from '@/types/api';

/**
 * 検査IDを指定して、検査の詳細情報を取得するAPI
 * [GET] /inspections/details
 * @param data { id: number } - 検査ID
 * @returns Promise<ApiResult<Inspection>>
 */
type InspectionDetailsRequest = {
  id: number;
};

export const fetchInspectionDetailsById = (
  data: InspectionDetailsRequest
): Promise<ApiResult<Inspection>> => {
  return api.get('/inspections/details', {
    params: { id: data.id },
  });
};

/**
 * 指定されたパス配下の全ての画像パスを取得するAPI
 * [GET] /inspections/all
 * @param data { path: string } - 画像フォルダのパス
 * @returns Promise<ApiResult<ImageListResponse>
 */
type ImageListRequest = {
  path: string;
};

type ImageListResponse = string[];

export const fetchAllImagesByPath = (
  data: ImageListRequest
): Promise<ApiResult<ImageListResponse>> => {
  return api.get('/inspections/all', {
    params: { path: data.path },
  });
};

/**
 * 画像IDを指定して、画像に関する詳細情報（例：エラー内容など）を取得するAPI
 * [GET] /inspections/details-img
 * @param data { id: number } - 画像ID
 * @returns Promise<ApiResult<ImageDetailsResponse>>
 */
type ImageDetailsRequest = {
  id: number;
};

export const fetchImageDetailsById = (
  data: ImageDetailsRequest
): Promise<ApiResult<InspectionDetailsImg>> => {
  return api.get('/inspections/details-img', {
    params: { id: data.id },
  });
};

/**
 * 検査IDと画像番号を指定して、その画像の全ての検査詳細情報を取得するAPI
 * [GET] /inspections/details-by-image
 * @param data { inspection_id: number, image_no: number } - 検査IDと画像番号
 * @returns Promise<ApiResult<InspectionDetailsImg[]>>
 */
type ImageDetailsByImageRequest = {
  inspection_id: number;
  image_no: number;
};

export const fetchImageDetailsByImage = (
  data: ImageDetailsByImageRequest
): Promise<ApiResult<InspectionDetailsImg[]>> => {
  return api.get('/inspections/details-by-image', {
    params: { 
      inspection_id: data.inspection_id,
      image_no: data.image_no 
    },
  });
};

/**
 * 検査IDを指定して、検査結果（OK/NGなど）を取得するAPI
 * [GET] /inspections/result
 * @param data { id: number } - 検査ID
 * @returns Promise<ApiResult<InspectionResult>>
 */
type InspectionResultRequest = {
  id: number;
};

export const fetchInspectionResultById = (
  data: InspectionResultRequest
): Promise<ApiResult<InspectionResult>> => {
  return api.get('/inspections/result', {
    params: { inspection_id: data.id },
  });
};

// Presentation images
export type PresentationImage = {
  id: number;
  inspection_id: number;
  group_name: string;
  image_path: string;
};

// fetchPresentationImages: call GET with inspection id, response ApiResult<PresentationImage[]>
export const fetchPresentationImages = (
  data: InspectionDetailsRequest
): Promise<ApiResult<PresentationImage[]>> => {
  return api.get(`/inspections/${data.id}/presentation-images`);
};

// Latest presentation images
export type LatestPresentationImagesResponse = {
  inspection_id: number;
  inspection_dt: string;
  images: PresentationImage[];
};

// fetchLatestPresentationImages: call GET to retrieve the latest inspection's presentation images
export const fetchLatestPresentationImages = (): Promise<ApiResult<LatestPresentationImagesResponse>> => {
  return api.get('/inspections/latest-presentation-images');
};

// Recent inspections for debug
export type RecentInspection = {
  inspection_id: number;
  inspection_dt: string;
  status: boolean;
};

// fetchRecentInspections: call GET to retrieve a list of recent inspections
export const fetchRecentInspections = (limit: number = 5): Promise<ApiResult<RecentInspection[]>> => {
  return api.get('/inspections/history-all', {
    params: { limit }
  });
};

// Inspection Settings types
export type InspectionSettings = {
  default_measurement: number;
  measurements: {
    no_defect: number;
    small_knot: number;
    large_knot: number;
    hole: number;
    discoloration: number;
  };
  ui: {
    textbox: {
      default_color: string;
      active_color: string;
    };
  };
};

// fetchInspectionSettings: call GET to retrieve the current inspection settings
export const fetchInspectionSettings = (): Promise<ApiResult<InspectionSettings>> => {
  return api.get('/inspections/settings');
};

// updateInspectionSettings: call POST to update inspection settings
export const updateInspectionSettings = (settings: Partial<InspectionSettings>): Promise<ApiResult<InspectionSettings>> => {
  return api.post('/inspections/settings', settings);
};