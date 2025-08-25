from datetime import datetime
from sqlalchemy import Integer
from sqlalchemy import String, text, ForeignKey, BIGINT
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship

if __package__ == "db":
    from .base import Base
else:
    from base import Base


class Dataset(Base):
    __tablename__ = "t_dataset"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="ID"
    )
    product_no: Mapped[str] = mapped_column(ForeignKey("t_product.product_no"))
    product = relationship("Product", back_populates="datasets")
    label: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="クラスラベル\n0:OK\n1:NG\n-1:未指定")
    file_path: Mapped[str] = mapped_column(
        String, nullable=False, comment="ファイルパス")

    # create_dt / update_dt
    create_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )
    update_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return f""
