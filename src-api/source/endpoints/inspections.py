import base64
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, WebSocket
from dependencies import get_session
from db import Inspection
from fastapi.encoders import jsonable_encoder
import asyncio
import json

router = APIRouter(prefix="/inspections")


@router.get(
    "/latest",
    description="最終検査情報取得",
)
def get_last_inspection(
    product_no: str = Query(title="品番"),
    session=Depends(get_session)
):
    try:
        # TODO: POLLINGではなくMYSQLに変更通知を任せるか検討
        with session:
            latest_inspection = session.query(Inspection).where(
                Inspection.product_no == product_no).order_by(Inspection.inspection_dt.desc()).first()
            if latest_inspection == None:
                return {"result": False, "message": "品番または検査情報が存在しません。"}
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


@router.websocket("/latest/{product_no}")
async def websocket_endpoint(websocket: WebSocket, product_no, session=Depends(get_session)):
    await websocket.accept()

    # 初期データを送信
    try:
        with session:
            inspection = session.query(Inspection).where(
                Inspection.product_no == product_no).order_by(Inspection.inspection_dt.desc()).first()
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

    async with connections_lock:
        if product_no not in websocket_connections:
            websocket_connections[product_no] = []
        websocket_connections[product_no].append(websocket)

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
            websocket_connections[product_no].remove(websocket)
            if len(websocket_connections[product_no]) == 0:
                # 接続クライアントが残ってない場合
                del websocket_connections[product_no]
        try:
            await websocket.close()
        except:
            pass
