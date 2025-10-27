from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Generic success response for operations that don't return data"""

    success: bool = True
    message: str = "Operation completed successfully"
