"""Domain exceptions mapped to HTTP status codes by the global exception handler."""


class DocIntelError(Exception):
    status_code = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthenticationError(DocIntelError):
    status_code = 401


class PermissionDeniedError(DocIntelError):
    status_code = 403


class NotFoundError(DocIntelError):
    status_code = 404


class ConflictError(DocIntelError):
    status_code = 409


class ValidationFailedError(DocIntelError):
    status_code = 422


class AIProviderError(DocIntelError):
    status_code = 502
