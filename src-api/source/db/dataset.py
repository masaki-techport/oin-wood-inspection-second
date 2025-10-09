from datetime import datetime

from sqlalchemy import String, DefaultClause, LargeBinary, ForeignKey, BIGINT
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship

if __package__ == "db":
    from .base import Base
else:
    from base import Base


class Dataset(Base):
    __tablename__ = "t_dataset"

    id: Mapped[int] = mapped_column(
        primary_key=True, nullable=False, autoincrement=True, comment="ID"
    )
    product_no: Mapped[str] = mapped_column(ForeignKey("t_product.product_no"))
    product = relationship("Product", back_populates="datasets")
    label: Mapped[int] = mapped_column(
        BIGINT, nullable=False, comment="クラスラベル\n0:OK\n1:NG\n-1:未指定")
    file_path: Mapped[str] = mapped_column(
        String, nullable=False, comment="ファイルパス")

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
