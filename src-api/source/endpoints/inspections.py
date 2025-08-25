import base64
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocket, HTTPException
from dependencies import get_session
from db import Inspection
from db import InspectionResult
from db.inspection_details import InspectionDetails
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
import asyncio
import json
import os
import yaml
from fastapi.responses import JSONResponse
from datetime import date
from sqlalchemy import desc, asc, func
from typing import List, Dict, Any, Optional
from db import InspectionPresentation
from __init__ import CONFIG_DIR

router = APIRouter(prefix="/inspections")


@router.get(
    "/latest",
    description="最終検査情報取得",
)
def get_last_inspection(
    session=Depends(get_session)
):
    try:
        # TODO: POLLINGではなくMYSQLに変更通知を任せるか検討
        with session:
            latest_inspection = session.query(Inspection).order_by(Inspection.inspection_dt.desc()).first()
            if latest_inspection == None:
                return {"result": False, "message": "検査情報が存在しません。"}
    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}
    # bytes型をbase64にエンコーディング
    # TODO: ミドルウェアなどに入れるか検討
    converted = jsonable_encoder(latest_inspection, custom_encoder={
        bytes: lambda o: base64.b64encode(o)
    })
    return {"result": True, "message": "Success!!", "data": converted}


websocket_connections = {}

connections_lock = asyncio.Semaphore(1)


@router.websocket("/latest")
async def websocket_endpoint(websocket: WebSocket, session=Depends(get_session)):
    await websocket.accept()

    # 初期データを送信
    try:
        with session:
            inspection = session.query(Inspection).order_by(Inspection.inspection_dt.desc()).first()
        if inspection:
            converted = jsonable_encoder(inspection, custom_encoder={
                bytes: lambda o: base64.b64encode(o).decode()
            })
            json_string = json.dumps(converted)
            await websocket.send_text(f"{json_string}")
        else:
            await websocket.send_text("null") 
    except:
        # データベース接続失敗、websocket切断などの場合は、ここで終了
        return

    connection_id = id(websocket)
    async with connections_lock:
        if "all" not in websocket_connections:
            websocket_connections["all"] = []
        websocket_connections["all"].append(websocket)

    try:
        while True:
            # 接続状態の確認処理
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.001)
            except asyncio.TimeoutError:
                pass
            else:
                pass
            await asyncio.sleep(0.5)
            
            # ここでは特に通知しない
            # 変更通知は変更チェックの処理内で行う
            # ここに渡すとタイムラグが発生するため

    except WebSocketDisconnect:
        async with connections_lock:
            websocket_connections["all"].remove(websocket)
            if len(websocket_connections["all"]) == 0:
                # 接続クライアントが残ってない場合
                del websocket_connections["all"]
        try:
            await websocket.close()
        except:
            pass

# =============================
# 検査詳細取得API
# 対象画面: inspection
# 対象ボタン: 検査結果詳細
# =============================
@router.get(
    "/details",
    description="指定IDの検査情報を取得",
)
def get_inspection_details(
    id: int = Query(..., description="検査ID"),
    session: Session = Depends(get_session),
):
    try:
        with session:
            inspection = session.query(Inspection).filter(Inspection.inspection_id == id).first()
            if inspection is None:
                return {"result": False, "message": "指定された検査情報が存在しません。"}
    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    # Encode bytes fields (例: 画像やバイナリデータがある場合)
    converted = jsonable_encoder(
        inspection,
        custom_encoder={
            bytes: lambda o: base64.b64encode(o).decode()  # decode() string
        },
    )

    return {"result": True, "message": "Success!!", "data": converted}

# =============================
# Get all Images API
# 対象画面: inspection-details
# 対象ボタン: list img
# =============================
@router.get(
    "/all",
    description="指定されたパスのフォルダ内の画像一覧を取得"
)
def get_image_list(
    path: str = Query(..., description="画像フォルダの相対パス（例: /uploads/abc）")
):
    try:
        # setting folder save img
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        BASE_IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")

        # join url
        folder_path = os.path.join(BASE_IMAGE_DIR, path.strip("/"))

        if not os.path.isdir(folder_path):
            return JSONResponse(content={
                "result": False,
                "message": f"フォルダが存在しません: {folder_path}"
            })

        # check file
        files = os.listdir(folder_path)
        image_files = [
            f for f in files
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))
        ]

        return {
            "result": True,
            "message": "Success!!",
            "data": image_files
        }

    except Exception as ex:
        return {
            "result": False,
            "message": f"Failed!! {ex}"
        }

# =============================
# API名       : 検査詳細取得API
# 対象画面    : inspection
# 対象アクション: 「検査結果詳細」ボタン押下時
# 説明        : 指定された検査IDに基づいて、検査情報および画像を取得する
# =============================
@router.get(
    "/details-img",
    description="指定IDの検査情報を取得（画像含む）"
)
def get_inspection_details(
    id: int = Query(..., description="検査ID（画像クリックで渡される）"),
    session: Session = Depends(get_session),
):
    try:
        with session:
            inspection = session.query(InspectionDetails).filter(InspectionDetails.error_id == id).first()
            if inspection is None:
                print("指定された検査情報が存在しません。")
                return  # None返すだけ
    except Exception as ex:
        print(f"Failed!! {ex}")
        return

    # Encode bytes fields (例: 画像やバイナリデータがある場合)
    converted = jsonable_encoder(
        inspection,
        custom_encoder={
            bytes: lambda o: base64.b64encode(o).decode()  # decode() string
        },
    )

    return {"result": True, "message": "Success!!", "data": converted}

# =============================
# Get inspection details by image API
# 対象画面: inspection-details
# 対象: 特定の画像の全ての検査詳細情報を取得
# =============================
@router.get(
    "/details-by-image",
    description="検査IDと画像番号を指定して、その画像の全ての検査詳細情報を取得"
)
def get_inspection_details_by_image(
    inspection_id: int = Query(..., description="検査ID"),
    image_no: int = Query(..., description="画像番号"),
    session: Session = Depends(get_session),
):
    try:
        with session:
            # Query all inspection details for the specific inspection and image number
            inspection_details = session.query(InspectionDetails).filter(
                InspectionDetails.inspection_id == inspection_id,
                InspectionDetails.image_no == image_no
            ).all()
            
            if not inspection_details:
                print(f"指定された検査情報が存在しません。inspection_id: {inspection_id}, image_no: {image_no}")
                return {"result": True, "message": "No inspection details found", "data": []}
                
    except Exception as ex:
        print(f"Failed!! {ex}")
        return {"result": False, "message": f"Failed to get inspection details: {ex}"}

    # Encode bytes fields for all inspection details
    converted_details = []
    for detail in inspection_details:
        converted = jsonable_encoder(
            detail,
            custom_encoder={
                bytes: lambda o: base64.b64encode(o).decode()
            },
        )
        converted_details.append(converted)

    return {"result": True, "message": "Success!!", "data": converted_details}

# =============================
# Get result status API
# 対象画面: inspection-details
# 対象: 節あり​, 穴・変色・腐れ発生​など
# =============================
@router.get(
    "/result",
    description="指定されたパスのフォルダ内の画像一覧を取得"
)
def get_result_status(
    inspection_id: int = Query(..., description="検査ID"),
    session: Session = Depends(get_session),
):
    try:
        with session:
            inspection = session.query(InspectionResult).filter(InspectionResult.inspection_id == inspection_id).first()
    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    # Encode bytes fields (例: 画像やバイナリデータがある場合)
    converted = jsonable_encoder(
        inspection,
        custom_encoder={
            bytes: lambda o: base64.b64encode(o).decode()  # decode() string
        },
    )

    return {"result": True, "message": "Success!!", "data": converted}


# =============================
# Get history API
# 対象画面: inspection-history
# 対象ボタン: calendarを押す
# =============================
@router.get(
    "/history",
    description="指定されたパスのフォルダ内の画像一覧を取得"
)
def get_history_by_date_like(
    date_selected: date = Query(..., description="指定日（YYYY-MM-DD）"),
    session: Session = Depends(get_session),
):
    try:
        with session:
            inspections = session.query(Inspection).filter(
                func.date(Inspection.inspection_dt) == date_selected
            ).all()
            
    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    converted = jsonable_encoder(
        inspections,
        custom_encoder={bytes: lambda o: base64.b64encode(o).decode()}
    )
    return {"result": True, "message": "Success!!", "data": converted}

# =============================
# Get history-all API
# 対象画面: inspection-history
# 対象ボタン: 最初に全部データを呼び出す
# =============================
@router.get(
    "/history-all",
    description="get all inspection"
)
def get_all_inspections(
    session: Session = Depends(get_session),
    limit: int = None,
):
    try:
        with session:
            query = session.query(Inspection).order_by(desc(Inspection.inspection_dt))
            
            # Apply limit if provided
            if limit is not None:
                query = query.limit(limit)
            
            inspections = query.all()
    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    converted = jsonable_encoder(
        inspections,
        custom_encoder={bytes: lambda o: base64.b64encode(o).decode()}
    )
    return {"result": True, "message": "Success!!", "data": converted}

# Simple in-memory cache for presentation images to reduce database load
_presentation_cache = {}
_cache_timestamps = {}

@router.get("/{inspection_id}/presentation-images")
async def get_presentation_images(inspection_id: int, session: Session = Depends(get_session)):
    """
    Get presentation images for the given inspection ID with simple caching
    """
    import time
    
    try:
        # Check cache first (cache for 2 seconds to handle rapid requests)
        current_time = time.time()
        cache_key = f"presentation_{inspection_id}"
        
        if (cache_key in _presentation_cache and 
            cache_key in _cache_timestamps and 
            current_time - _cache_timestamps[cache_key] < 2):
            print(f"Returning cached presentation images for inspection {inspection_id}")
            return _presentation_cache[cache_key]
        
        # Query the presentation images for the given inspection ID
        presentation_images = session.query(InspectionPresentation).filter(
            InspectionPresentation.inspection_id == inspection_id
        ).all()
        
        # Debug: Print presentation images data
        print(f"DEBUG: Found {len(presentation_images)} presentation images for inspection {inspection_id}")
        for img in presentation_images:
            print(f"  ID: {img.id}, Group: {img.group_name}, Path: {img.image_path}")
            
        # Check for duplicates
        group_counts = {}
        for img in presentation_images:
            group_counts[img.group_name] = group_counts.get(img.group_name, 0) + 1
        
        duplicate_groups = [group for group, count in group_counts.items() if count > 1]
        if duplicate_groups:
            print(f"WARNING: Found duplicate groups: {duplicate_groups}")
            for group in duplicate_groups:
                duplicates = [img for img in presentation_images if img.group_name == group]
                print(f"  Group {group} duplicates:")
                for dup in duplicates:
                    print(f"    ID: {dup.id}, Path: {dup.image_path}")
        
        # If no presentation images found, return empty list
        if not presentation_images:
            result = {"result": True, "message": "No presentation images found", "data": []}
        else:
            # Convert to list of dictionaries for JSON response
            presentation_data = [
                {
                    "id": image.id,
                    "inspection_id": image.inspection_id,
                    "group_name": image.group_name,
                    "image_path": image.image_path,
                }
                for image in presentation_images
            ]
            result = {"result": True, "message": "Success", "data": presentation_data}
        
        # Cache the result
        _presentation_cache[cache_key] = result
        _cache_timestamps[cache_key] = current_time
        
        # Clean up old cache entries (keep only last 10)
        if len(_presentation_cache) > 10:
            oldest_key = min(_cache_timestamps.keys(), key=lambda k: _cache_timestamps[k])
            del _presentation_cache[oldest_key]
            del _cache_timestamps[oldest_key]
        
        return result
        
    except Exception as e:
        print(f"Error getting presentation images for inspection {inspection_id}: {str(e)}")
        return {"result": False, "message": f"Failed to get presentation images: {str(e)}"}

@router.get("/latest-presentation-images")
async def get_latest_presentation_images(session: Session = Depends(get_session)):
    """
    Get presentation images for the latest inspection with simple caching
    """
    import time
    
    try:
        # Check cache first (cache for 1 second to handle rapid requests)
        current_time = time.time()
        cache_key = "latest_presentation"
        
        if (cache_key in _presentation_cache and 
            cache_key in _cache_timestamps and 
            current_time - _cache_timestamps[cache_key] < 1):
            print("Returning cached latest presentation images")
            return _presentation_cache[cache_key]
        
        # Get the latest inspection ID
        latest_inspection = session.query(Inspection).order_by(desc(Inspection.inspection_dt)).first()
        
        if not latest_inspection:
            result = {"result": False, "message": "No inspections found"}
        else:
            # Query the presentation images for the latest inspection ID
            presentation_images = session.query(InspectionPresentation).filter(
                InspectionPresentation.inspection_id == latest_inspection.inspection_id
            ).all()
            
            # If no presentation images found, return empty list with inspection ID
            if not presentation_images:
                result = {
                    "result": True, 
                    "message": "No presentation images found for the latest inspection", 
                    "data": {
                        "inspection_id": latest_inspection.inspection_id,
                        "inspection_dt": latest_inspection.inspection_dt.isoformat() if latest_inspection.inspection_dt else None,
                        "images": []
                    }
                }
            else:
                # Convert to list of dictionaries for JSON response
                presentation_data = [
                    {
                        "id": image.id,
                        "inspection_id": image.inspection_id,
                        "group_name": image.group_name,
                        "image_path": image.image_path,
                    }
                    for image in presentation_images
                ]
                
                result = {
                    "result": True, 
                    "message": "Success", 
                    "data": {
                        "inspection_id": latest_inspection.inspection_id,
                        "inspection_dt": latest_inspection.inspection_dt.isoformat() if latest_inspection.inspection_dt else None,
                        "images": presentation_data
                    }
                }
        
        # Cache the result
        _presentation_cache[cache_key] = result
        _cache_timestamps[cache_key] = current_time
        
        return result
        
    except Exception as e:
        print(f"Error getting latest presentation images: {str(e)}")
        return {"result": False, "message": f"Failed to get latest presentation images: {str(e)}"}


@router.get("/settings")
async def get_inspection_settings():
    """
    Get measurement settings and UI configuration for the inspection screen
    from the inspections.yaml file.
    
    Returns settings for:
    - Default measurement value
    - Measurement values for different defect types
    - UI display settings (textbox colors, etc.)
    """
    try:
        # Get the path to the inspections.yaml file using centralized config directory
        config_file = os.path.join(CONFIG_DIR, 'inspections.yaml')
        
        # Default settings in case file is not found or has missing values
        default_settings = {
            "default_measurement": 45,
            "measurements": {
                "no_defect": 45,
                "small_knot": 45,
                "large_knot": 45,
                "hole": 45,
                "discoloration": 45
            },
            "ui": {
                "textbox": {
                    "default_color": "lightgray",
                    "active_color": "white"
                }
            }
        }
        
        # Load settings from file if it exists
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                settings = yaml.safe_load(f)
                
            # Merge with defaults to ensure all expected keys exist
            if settings:
                # Handle measurements section
                if "measurements" not in settings:
                    settings["measurements"] = default_settings["measurements"]
                else:
                    for key, value in default_settings["measurements"].items():
                        if key not in settings["measurements"]:
                            settings["measurements"][key] = value
                
                # Handle UI section
                if "ui" not in settings:
                    settings["ui"] = default_settings["ui"]
                elif "textbox" not in settings["ui"]:
                    settings["ui"]["textbox"] = default_settings["ui"]["textbox"]
                else:
                    for key, value in default_settings["ui"]["textbox"].items():
                        if key not in settings["ui"]["textbox"]:
                            settings["ui"]["textbox"][key] = value
                
                # Handle default_measurement
                if "default_measurement" not in settings:
                    settings["default_measurement"] = default_settings["default_measurement"]
            else:
                settings = default_settings
        else:
            # Use default settings if file doesn't exist
            settings = default_settings
            
        return {
            "result": True,
            "message": "Inspection settings loaded successfully",
            "data": settings
        }
        
    except Exception as e:
        print(f"Error loading inspection settings: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "result": False,
            "message": f"Failed to load inspection settings: {str(e)}"
        }


class InspectionSettingsUpdate(BaseModel):
    """Pydantic model for inspection settings update request"""
    default_measurement: Optional[int] = None
    measurements: Optional[Dict[str, int]] = None
    ui: Optional[Dict[str, Dict[str, str]]] = None


@router.post("/settings")
async def update_inspection_settings(settings_update: InspectionSettingsUpdate):
    """
    Update measurement settings and UI configuration in the inspections.yaml file.
    
    Only updates the fields provided in the request body.
    """
    try:
        # Get the path to the inspections.yaml file using centralized config directory
        config_file = os.path.join(CONFIG_DIR, 'inspections.yaml')
        
        # First load current settings
        current_settings = {}
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                current_settings = yaml.safe_load(f) or {}
        
        # Update settings with new values
        if settings_update.default_measurement is not None:
            current_settings["default_measurement"] = settings_update.default_measurement
            
        if settings_update.measurements:
            if "measurements" not in current_settings:
                current_settings["measurements"] = {}
            for key, value in settings_update.measurements.items():
                current_settings["measurements"][key] = value
                
        if settings_update.ui:
            if "ui" not in current_settings:
                current_settings["ui"] = {}
            for section_key, section_value in settings_update.ui.items():
                if section_key not in current_settings["ui"]:
                    current_settings["ui"][section_key] = {}
                for key, value in section_value.items():
                    current_settings["ui"][section_key][key] = value
        
        # Ensure directory exists
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # Write updated settings back to file
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(current_settings, f, default_flow_style=False)
            
        return {
            "result": True,
            "message": "Inspection settings updated successfully",
            "data": current_settings
        }
        
    except Exception as e:
        print(f"Error updating inspection settings: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "result": False,
            "message": f"Failed to update inspection settings: {str(e)}"
        }