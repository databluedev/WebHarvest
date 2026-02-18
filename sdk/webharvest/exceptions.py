"""Exception classes for the WebHarvest SDK."""


class WebHarvestError(Exception):
    """Base exception for all WebHarvest SDK errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code that triggered the error, if applicable.
        response_body: Raw response body from the API, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class AuthenticationError(WebHarvestError):
    """Raised when the API returns a 401 Unauthorized response.

    This typically means the token is missing, expired, or invalid.
    """


class NotFoundError(WebHarvestError):
    """Raised when the API returns a 404 Not Found response.

    The requested resource (job, schedule, etc.) does not exist
    or is not accessible to the current user.
    """


class RateLimitError(WebHarvestError):
    """Raised when the API returns a 429 Too Many Requests response.

    The caller has exceeded the allowed request rate. Retry after
    the period indicated by the Retry-After header, if present.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = 429,
        response_body: dict | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code, response_body)
        self.retry_after = retry_after


class ServerError(WebHarvestError):
    """Raised when the API returns a 5xx server error response.

    An unexpected error occurred on the server side.
    """


class JobFailedError(WebHarvestError):
    """Raised when a polled job completes with an error status.

    Attributes:
        job_id: The ID of the failed job.
    """

    def __init__(
        self,
        message: str,
        job_id: str | None = None,
        response_body: dict | None = None,
    ) -> None:
        super().__init__(message, status_code=None, response_body=response_body)
        self.job_id = job_id


class TimeoutError(WebHarvestError):
    """Raised when polling for a job exceeds the specified timeout.

    Attributes:
        job_id: The ID of the job that timed out.
        elapsed: Number of seconds elapsed before the timeout was raised.
    """

    def __init__(
        self,
        message: str,
        job_id: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        super().__init__(message, status_code=None)
        self.job_id = job_id
        self.elapsed = elapsed
