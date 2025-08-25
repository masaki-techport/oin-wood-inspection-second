if __name__ == "__main__":
    from engine import engine
    from product import Product
    from inspection import Inspection
    from dataset import Dataset
    from sqlalchemy.orm import Session
    import os
    import sys
    import random
    import string
    from datetime import datetime

    def png_to_bytes(file_path):
        with open(file_path, 'rb') as file:
            byte_data = file.read()
        return byte_data

    with Session(engine) as session:

        # create random car_no and car_model
        product_no = "".join(random.choices(string.ascii_uppercase, k=10))
        product_name = "productname_" + "".join(
            random.choices(string.ascii_letters + string.digits, k=5)
        )
        current_dir = os.path.dirname(os.path.abspath(__file__))

        assets_path = os.path.abspath(
            os.path.join(current_dir, '..', '..', 'assets'))
        product_image = png_to_bytes(os.path.join(
            assets_path, "test_product_image.png"))

        # insert
        results = Product.add(
            session,
            product_no=product_no,
            product_name=product_name,
            file_path="data/images/product/test_product_image.png"
        )
        new_id = results["data"].product_no

        inspection_image = png_to_bytes(os.path.join(
            assets_path, "test_inspection_image.png"))
        # select
        results = Inspection.add(
            session,
            product_no=new_id,
            serial="serial",
            inspection_dt=datetime.now(),
            file_path="data/images/inspection/test_inspection_image.png")

        results = Inspection.add(
            session,
            product_no=new_id,
            serial="serial1",
            inspection_dt=datetime.now(),
            file_path="data/images/inspection/test_inspection_image.png")

        results = Dataset.add(
            session,
            product_no=new_id,
            label=1,
            file_path="data/images/dataset/test_inspection_image.png"
        )
        results = Dataset.add(
            session,
            product_no=new_id,
            label=2,
            file_path="data/images/dataset/test_inspection_image.png"
        )

        session.commit()
