import sqlalchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql._typing import _ColumnExpressionArgument

from datetime import datetime


class Base(DeclarativeBase):
    """base class
    ベースクラス
    """

    type_annotation_map = {
        int: sqlalchemy.BIGINT,
        datetime: sqlalchemy.TIMESTAMP(timezone=True),
        str: sqlalchemy.String().with_variant(sqlalchemy.NVARCHAR, "mssql"),
        bytes: sqlalchemy.LargeBinary,
        bool: sqlalchemy.Boolean
    }

    def to_dict(self) -> dict:
        """convert to dict
            レコードデータをdictに変換する
        Returns:
            dict: dict
        """
        keys = [x for x in vars(self) if x[0] != "_"]
        return {k: getattr(self, k) for k in keys}

    @classmethod
    def add(cls, session, auto_commit=False, **kwargs):
        """simple add method
            シンプルな追加メソッド

        Args:
            session (Session): セッション
            auto_commit (bool, optional): コミットフラグ. Defaults to False.
            **kwargs: 追加内容

        Returns:
            {
                result (bool): 結果
                message (str): メッセージ
                new_item (Any): 追加したレコード
            }
        """
        try:
            # add
            item = cls(**kwargs)
            session.add(item)
            if auto_commit:
                session.commit()
            session.flush()
            return {"result": True, "message": "Insert Success!!", "data": item}
        except Exception as ex:
            if auto_commit:
                session.rollback()
            return {"result": False, "message": f"Insert Failed!! {ex}"}

    @classmethod
    def update(
        cls,
        session,
        *criterion: _ColumnExpressionArgument[bool],
        auto_commit=False,
        **kwargs,
    ):
        """simple update method
            シンプルな更新メソッド

        Args:
            session (Session): セッション
            auto_commit (bool, optional): コミットフラグ. Defaults to False.
            *criterion (_ColumnExpressionArgument[bool]): 抽出条件
            **kwargs: 更新内容

        Returns:
            {
                result (bool): 結果
                message (str): メッセージ
            }
        """
        try:
            # update
            session.query(cls).filter(*criterion).update(kwargs)
            if auto_commit:
                session.commit()
            session.flush()

            return {"result": True, "message": "Update Success!!"}
        except Exception as ex:
            if auto_commit:
                session.rollback()
            return {"result": False, "message": f"Update Failed!! {ex}"}

    @classmethod
    def delete(
        cls, session, *criterion: _ColumnExpressionArgument[bool], auto_commit=False
    ):
        """simple delete method
            シンプルな削除メソッド

        Args:
            session (Session): セッション
            *criterion (_ColumnExpressionArgument[bool]): 抽出条件

        Returns:
            {
                result (bool): 結果
                message (str): メッセージ
            }
        """
        try:
            # delete
            session.query(cls).filter(*criterion).delete()
            if auto_commit:
                session.commit()
            session.flush()
            return {"result": True, "message": "Delete Success!!"}
        except Exception as ex:
            if auto_commit:
                session.rollback()
            return {"result": False, "message": f"Delete Failed!! {ex}"}

    @classmethod
    def select_all(
        cls,
        session: sqlalchemy.orm.Session,
        *criterion: _ColumnExpressionArgument[bool],
    ):
        """simple select method
            シンプルな抽出メソッド

        Args:
            session (Session): セッション
            *criterion (_ColumnExpressionArgument[bool]): 抽出条件

        Returns:
            {
                result (bool): 結果
                message (str): メッセージ
                records (List[dict]): レコードリスト
            }
        """
        try:
            results = []
            # select
            stmt = sqlalchemy.Select(cls).filter(*criterion)
            for row in session.scalars(stmt):
                results.append(row.to_dict())
            return {"result": True, "message": "Select Success!!", "records": results}
        except Exception as ex:
            return {"result": False, "message": f"Select Failed!! {ex}", "records": []}
