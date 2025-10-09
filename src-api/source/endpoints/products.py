import pytz
import base64
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
import sqlalchemy
from dependencies import get_session
from db import Product
from fastapi.encoders import jsonable_encoder
from models import ProductModel
from datetime import datetime
import os
import uuid
from app_config import APP_CONFIG
from sqlalchemy import exists

router = APIRouter(prefix="/products")

jp_timezone = pytz.timezone('Asia/Tokyo')

def get_file_extension(filename: str) -> str:
    _, extension = os.path.splitext(filename)
    return extension

@router.get(
    "",
    description="品番リスト取得",
)
def get_product(product_no: str = Query(default="", title="品番"),
                product_name: str = Query(default="", title="品名"),
                page_no: int = Query(default=1, title="ページNo"),
                page_size: int = Query(default=10, title="ページサイズ"),
                from_dt: datetime = Query(default=None),
                to_dt: datetime = Query(default=None),
                order_by: str = Query(default=None),
                order: str = Query(default="asc"),
                session=Depends(get_session)):
    try:
        from_dt = from_dt.replace(tzinfo=pytz.utc).astimezone(
            jp_timezone) if from_dt else from_dt
        to_dt = to_dt.replace(tzinfo=pytz.utc).astimezone(
            jp_timezone) if to_dt else to_dt
        with session:
            # product_noを指定してproductを取得
            query = session.query(Product)
            if product_no:
                query = query.filter(
                    Product.product_no.like(f"%{product_no}%"))
            if product_name:
                query = query.filter(
                    Product.product_name.like(f"%{product_name}%"))
            if from_dt:
                query = query.filter(Product.create_dt >= from_dt)
            if to_dt:
                query = query.filter(Product.create_dt <= to_dt)

            if order_by:
                if order_by == "product_no":
                    query = query.order_by(Product.product_no.asc(
                    ) if order == "asc" else Product.product_no.desc())
                elif order_by == "product_name":
                    query = query.order_by(Product.product_name.asc(
                    ) if order == "asc" else Product.product_name.desc())
                elif order_by == "create_dt":
                    query = query.order_by(Product.create_dt.asc(
                    ) if order == "asc" else Product.create_dt.desc())

            total_count = query.count()

            offset = (page_no - 1) * page_size

            # ページNoがおかしい
            if total_count != 0 and offset >= total_count:
                page_no = 1
                offset = 0

            query = query.slice(offset, offset + page_size)

            results = query.all()

    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    # JSONエンコーディング
    converted_results = jsonable_encoder(results)
    return {
        "result": True,
        "message": "Success!!",
        "data": converted_results,
        "total_count": total_count,
        "page_no": page_no,
        "page_size": page_size
    }

@router.get(
    "/{product_no}",
    description="product_noを指定してproductを取得",
)
def get_product(product_no: str, session=Depends(get_session)):
    try:
        with session:
            product = session.query(Product).filter_by(
                product_no=product_no).first()
            if product is None:
                return {"result": False, "message": "品番が存在しません"}

    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}

    # JSONエンコーディング
    converted = jsonable_encoder(product)
    return {"result": True, "message": "Success!!", "data": converted}

@router.post(
    "",
    description="製品情報追加",
)

async def create_product(
    product_no: str = Form(...),
    product_name: str = Form(...),
    product_file: UploadFile = File(default=None),
    session=Depends(get_session)
):
    try:
        with session:
            # Check if the product_no already exists
            is_exists = session.query(exists().where(
                Product.product_no == product_no)).scalar()
            if is_exists:
                return {"result": False, "message": "品番が存在しています。"}
            if product_name is None:
                return {"result": False, "message": "品名が必須です。"}
            # Save the uploaded file
            file_path = None
            
            if product_file:
                # Ensure you're reading the file in binary mode
                file_extension = get_file_extension(product_file.filename)
                uuid4 = uuid.uuid4()
                file_path = os.path.join(
                    APP_CONFIG['upload_folder_product'], f"{str(uuid4)}{file_extension}")
                
                # Open file in binary write mode
                with open(file_path, "wb") as buffer:
                    buffer.write(await product_image.read())

            # Add product to the database
            add_product = {
                "product_no": product_no,
                "product_name": product_name,
                "file_path": file_path
            }
            results = Product.add(session, **add_product)
            if results["result"] is False:
                session.rollback()
            else:
                session.commit()

            return results

    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}


@router.patch(
    "",
    description="製品情報更新",
)
async def update_product(
    product_no: str = Form(...),
    product_name: str = Form(default=None),
    product_file: UploadFile = File(default=None),
    session=Depends(get_session)
):
    try:
        with session:
            product = session.query(Product).filter_by(
                product_no=product_no).first()
            if product:
                if product_name is not None:
                    product.product_name = product_name

                # ファイルの更新
                if product_file:
                    file_extension = get_file_extension(product_file.filename)
                    uuid4 = uuid.uuid4()
                    file_path = os.path.join(
                        APP_CONFIG['upload_folder_product'], f"{str(uuid4)}{file_extension}")
                    with open(file_path, "wb") as buffer:
                        buffer.write(await product_file.read())

                    # 古いファイルを削除
                    if product.file_path and os.path.exists(product.file_path):
                        os.remove(product.file_path)

                    # 新しいファイルパスを保存
                    product.file_path = file_path

                session.commit()
            else:
                return {"result": False, "message": "品番が存在しません。"}

    except Exception as ex:
        session.rollback()
        return {"result": False, "message": f"Failed!! {ex}"}

    return {"result": True, "message": "Success!!"}

@router.delete(
    "/{product_no}",
    description="品番を削除",
)
def delete_product(product_no: str, session=Depends(get_session)):
    try:
        with session:
            product = session.query(Product).filter_by(
                product_no=product_no).first()
            if product:
                if product.file_path and os.path.exists(product.file_path):
                    os.remove(product.file_path)

            results = Product.delete(session, Product.product_no == product_no)
            if results["result"] is False:
                # 失敗した場合はロールバック
                session.rollback()
            else:
                session.commit()
            return results

    except Exception as ex:
        return {"result": False, "message": f"Failed!! {ex}"}
