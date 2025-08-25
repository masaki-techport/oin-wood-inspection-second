from datetime import datetime
from sqlalchemy import String, text
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship

if __package__ == "db":
    from .base import Base
else:
    from base import Base


class Product(Base):
    __tablename__ = "t_product"

    product_no: Mapped[str] = mapped_column(
        String(10), primary_key=True, nullable=False, comment="品番"
    )
    product_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="品名"
    )
    file_path: Mapped[str] = mapped_column(
        String, nullable=True, comment="ファイルパス" 
    )

    # create_dt / update_dt
    create_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )
    update_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    datasets = relationship("Dataset", back_populates="product")

    def __repr__(self) -> str:
        return f"Product(品番={self.product_no!r}, 品名={self.product_name!r}, ファイルパス={self.file_path!r})"

if __name__ == "__main__":
    from engine import engine

    with Session(engine) as session:
        import random
        import string
        import os

        # create random product_no and product_name
        product_no = "".join(random.choices(string.ascii_uppercase, k=10))
        product_name = "productname_" + "".join(
            random.choices(string.ascii_letters + string.digits, k=5)
        )
        file_path = "data/images/test_product_image.png"

        # Insert
        results = Product.add(
            session,
            product_no=product_no,
            product_name=product_name,
            file_path=file_path 
        )
        print("Insert: ", results)

        if results["result"]:
            new_id = results["new_item"].product_no

            # Select
            results = Product.select_all(session, Product.product_no == new_id)
            print("Insert record: ", results["records"][0])

            # Update
            new_file_path = "data/images/test_product_image.png"
            
            if not os.path.exists(os.path.dirname(new_file_path)):
                os.makedirs(os.path.dirname(new_file_path))
            with open(new_file_path, 'wb') as f:
                f.write(bytes([random.randint(0, 255) for _ in range(100)]))

            results = Product.update(
                session,
                Product.product_no == new_id,
                product_name="new_name",
                file_path=new_file_path, 
            )
            print("Update: ", results)

            # Select
            results = Product.select_all(session, Product.product_no == new_id)
            print("Update record: ", results["records"][0])

            # Delete
            results = Product.delete(session, Product.product_no == new_id)
            print("Delete: ", results)

            # Select
            results = Product.select_all(session, Product.product_no == new_id)
            print("Delete record: ", results["records"])

            # Rollback in case of issues
            session.rollback()
