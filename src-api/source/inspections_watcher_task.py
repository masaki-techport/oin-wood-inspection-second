from functools import reduce
from dependencies import get_session
from db import Inspection
from endpoints.inspections import websocket_connections
from sqlalchemy.sql import func
from sqlalchemy import desc
from fastapi.encoders import jsonable_encoder
import base64
import json
import asyncio

async def inspections_watcher_task():
    # !!! 検査情報あり→なしのケースは考慮していない
    prev_inspection = {}  # product_no -> latest_inspection_id
    while True:
        try:
            # # DEBUG LOG
            # for key, value in websocket_connections.items():
            #     value_str = reduce(
            #         lambda x, y: x + f"{y.client.host}:{y.client.port}, ", value, "")
            #     print(f"Product No【{key}】：[{value_str}]")

            list_product_no = websocket_connections.keys()
            if (len(list_product_no) > 0):
                with next(get_session()) as session:
                    # 品番ごとの最終検査ID取得(IDのみ)
                    subq = session.query(
                        func.row_number().over(partition_by=Inspection.product_no,
                                                order_by=desc(Inspection.inspection_dt)).label('rn'),
                        Inspection.inspection_id,
                        Inspection.product_no
                    ).filter(Inspection.product_no.in_(list_product_no)).subquery()
                    latest_inspections = session.query(
                        subq.c.inspection_id, subq.c.product_no).filter(subq.c.rn == 1).all()

                    # 検査ID変更チェック
                    changed_inspections_id = {}  # 品番ごとの変更検査ID
                    for inspection_id, product_no in latest_inspections:
                        if (product_no not in prev_inspection or prev_inspection[product_no] != inspection_id):
                            changed_inspections_id[product_no] = inspection_id

                    # 変更した検査詳細情報
                    changed_inspections = session.query(Inspection).where(
                        Inspection.inspection_id.in_(changed_inspections_id.values())).all()

                # 変更した検査詳細情報をdict型に変換、json変換 品番→json検査情報
                changed_inspections_dict = {}
                for inspection in changed_inspections:
                    converted = jsonable_encoder(inspection, custom_encoder={
                        bytes: lambda o: base64.b64encode(o).decode()
                    })
                    json_string = json.dumps(converted)
                    changed_inspections_dict[inspection.product_no] = json_string

                async def ignore_exception_wrapper(func, *args, **kwargs):
                    try:
                        await func(*args, **kwargs)
                    except:
                        pass

                # 変更検査を通知
                for product_no, inspection in changed_inspections_dict.items():
                    # 変更品番で接続しているクライアントに通知
                    try:
                        # 通知処理は待たずに非同期で行う
                        for client in websocket_connections[product_no]:
                            asyncio.create_task(ignore_exception_wrapper(
                                client.send_text, f"{inspection}"))
                    except:
                        # 途中で品番のすべてのクライアントが切断されたかもしれない
                        pass

                # 前回データを更新
                prev_inspection = {}
                for inspection_id, product_no in latest_inspections:
                    prev_inspection[product_no] = inspection_id

            await asyncio.sleep(0.5)
        except:
            # 例外の場合、DB接続失敗の時などは無視
            # TODO: 切断時のクライアント側のリトライ仕組みを実装？
            pass