import json
import logging
import traceback
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)

class JSONExceptionMiddleware:
    """
    Middleware to handle exceptions and return JSON responses for API calls
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Process exceptions and return JSON response for API requests
        """
        if request.path.startswith('/api/'):
            logger.error(f"Exception in {request.path}: {str(exception)}")
            logger.error(traceback.format_exc())
            
            status_code = 500
            
            if hasattr(exception, 'status_code'):
                status_code = exception.status_code
            
            # Build error response
            error_data = {
                'error': True,
                'message': str(exception),
                'status_code': status_code
            }
            
            if settings.DEBUG:
                error_data['traceback'] = traceback.format_exc()
            
            return JsonResponse(error_data, status=status_code)
        
        return None


# exceptions.py
class XBRLError(Exception):
    """Base exception for XBRL errors"""
    status_code = 400
    
    def __init__(self, message, status_code=None):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class XBRLValidationError(XBRLError):
    """Raised when XBRL data validation fails"""
    status_code = 400
    
    def __init__(self, validation_errors, message=None):
        self.validation_errors = validation_errors
        if message is None:
            message = "XBRL validation failed"
        super().__init__(message, self.status_code)
    
    def to_dict(self):
        return {
            'message': self.message,
            'validation_errors': self.validation_errors
        }


class XBRLProcessingError(XBRLError):
    """Raised when there's an error processing XBRL data"""
    status_code = 500
    
    def __init__(self, message=None, original_exception=None):
        self.original_exception = original_exception
        if message is None:
            message = "Error processing XBRL data"
        if original_exception:
            message = f"{message}: {str(original_exception)}"
        super().__init__(message, self.status_code)

