from fastapi import APIRouter, Depends, Query, File, UploadFile, Form
from dependencies import get_session
from db import Product, Dataset
from sqlalchemy import exists
from typing import List
import uuid
import os
from app_config import APP_CONFIG
import json
from pathlib import Path

router = APIRouter(prefix="/datasets")


def get_file_extension(filename: str) -> str:
    _, extension = os.path.splitext(filename)
    return extension


@router.get(
    "",
    description="データセット取得",
)
def get_datasets(
    product_no: str = Query(title="品番"),
    session=Depends(get_session)
):
    try:
        with session:
            is_exists = session.query(exists().where(
                Product.product_no == product_no)).scalar()
            if not is_exists:
                return {"result": False, "message": "品番が存在しません。"}
            datasets = session.query(Dataset.id, Dataset.label, Dataset.file_path).filter(
                Dataset.product_no == product_no).all()
            result_dict = [x._mapping for x in datasets]

    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    return {"result": True, "message": "Success!!", "data": result_dict}


@router.post(
    "",
    description="データセット追加・修正・削除",
)
async def update_datasets(
    product_no: str = Form(...),
    datasets_json: str = Form(...),
    files: List[UploadFile] = File(default=None),
    session=Depends(get_session)
):
    saved_files = []
    try:
        datasets = json.loads(datasets_json)
        # TODO: データセットのヴァリデーション
        # （ラベル、更新の場合、idはついているか、ファイル数とadd数があっているか、など）
        deleted_images = []
        with session:
            is_exists = session.query(exists().where(
                Product.product_no == product_no)).scalar()
            if not is_exists:
                raise Exception("品番が存在しません。")
            if (files):
                for file in files:
                    file_extension = get_file_extension(file.filename)
                    uuid4 = uuid.uuid4()
                    image_path = os.path.join(
                        APP_CONFIG['upload_folder_dataset'], f"{str(uuid4)}.{file_extension}")
                    with open(image_path, "wb") as buffer:
                        buffer.write(await file.read())
                    saved_files.append(image_path)

            for dataset in datasets:
                if (dataset["action"] == "add"):
                    dataset_add = {}
                    dataset_add["product_no"] = product_no
                    dataset_add["label"] = dataset["label"]
                    dataset_add["file_path"] = saved_files[dataset["file_index"]]
                    result = Dataset.add(session, **dataset_add)
                    if (not result["result"]):
                        raise Exception(result["message"])
                elif (dataset["action"] == "update"):
                    dataset_db = session.query(Dataset).filter_by(
                        id=dataset["id"]).first()
                    if dataset_db:
                        dataset_db.label = dataset["label"]
                    else:
                        raise Exception("データセットが存在しません。")
                elif (dataset["action"] == "delete"):
                    dataset_db = session.query(Dataset).filter_by(
                        id=dataset["id"]).first()
                    if dataset_db:
                        session.delete(dataset_db)
                        deleted_images.append(dataset_db.file_path)
                    else:
                        raise Exception("データセットが存在しません。")
                else:
                    raise Exception("操作不正？")

            session.commit()
            # データベース更新成功の場合
            for image in deleted_images:
                try:
                    if os.path.exists(image):
                        os.remove(image)
                except:  # 削除失敗の場合は無視
                    pass

    except Exception as ex:
        for file in saved_files:
            if os.path.exists(file):
                os.remove(file)
        session.rollback()
        return {"result": False, "message": f"{ex}"}

    return {"result": True, "message": "Success!!"}
