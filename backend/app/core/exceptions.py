class AppException(Exception):
    def __init__(self, message: str, *, code: int = 40000, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundException(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=40400, status_code=404)


class ConflictException(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=40900, status_code=409)


class StorageException(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=50200, status_code=502)
