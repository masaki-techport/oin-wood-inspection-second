from datetime import datetime

from sqlalchemy import String, DefaultClause, LargeBinary, ForeignKey, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

if __package__ == "db":
    from .base import Base
else:
    from base import Base


class Inspection(Base):
    __tablename__ = "t_inspection"

    inspection_id: Mapped[int] = mapped_column(
        primary_key=True, nullable=False, autoincrement=True, comment="検査トランザクションID"
    )
    product_no: Mapped[str] = mapped_column(ForeignKey("t_product.product_no"))
    serial: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="シリアル")
    inspection_dt: Mapped[datetime] = mapped_column(
        nullable=False, comment="更新日時")
    inspection_result: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="検査結果")
    file_path: Mapped[str] = mapped_column(
        String, nullable=True, comment="ファイルパス" 
    )

    # create_dt / update_dt
    create_dt: Mapped[datetime] = mapped_column(
        server_default=DefaultClause("CURRENT_TIMESTAMP")
    )
    update_dt: Mapped[datetime] = mapped_column(
        server_default=DefaultClause("CURRENT_TIMESTAMP"),
        server_onupdate=DefaultClause("CURRENT_TIMESTAMP", for_update=True),
    )

    def __repr__(self) -> str:
        return f""


if __name__ == "__main__":
    from engine import engine
    from product import Product

    with Session(engine) as session:
        import random
        import string

        # create random car_no and car_model
        product_no = "".join(random.choices(string.ascii_uppercase, k=10))
        product_name = "productname_" + "".join(
            random.choices(string.ascii_letters + string.digits, k=5)
        )
        file_path = "data/images/test_inspection_image.png"

        # insert
        results = Product.add(
            session,
            product_no=product_no,
            product_name=product_name,
            file_path=file_path
        )
        print("insert: ", results)
        new_id = results["new_item"].product_no

        # select
        results = Inspection.add(
            session,
            product_no=new_id,
            serial="serial",
            inspection_dt=datetime.now(),
            inspection_result=False,
            file_path=file_path)
        print("insert record: ", results)

        # rollback
        session.rollback()
