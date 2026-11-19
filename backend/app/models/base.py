"""
SQLAlchemy 2.0 模型基类

所有 model 都继承这里的 Base（从 app.database 导入）。
"""
from app.database import Base

__all__ = ["Base"]