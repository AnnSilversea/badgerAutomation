"""Exceptions used by karbon_api."""


class KarbonAPIError(RuntimeError):
    """Raised when Karbon API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str, *, response_text: str = ""): 
        super().__init__(f"Karbon API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response_text = response_text
