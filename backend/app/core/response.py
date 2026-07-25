from typing import Generic, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 0
    msg: str = "成功"
    data: DataT | None = None


def success_response(data: DataT | None = None, msg: str = "成功") -> ApiResponse[DataT]:
    return ApiResponse(code=0, msg=msg, data=data)
