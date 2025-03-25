import json
import uuid
import logfire
from ..agent import financial_statement_agent
from ..dependencies import financial_deps
from .storage import map_pydantic_to_django_fields, store_mapped_data_to_db

class XBRLProcessor:
    """Base processor for XBRL data"""
    def process_async(self, data):
        """
        Simulates asynchronous processing but actually runs synchronously.
        Kept for API compatibility with previous implementation.
        
        Args:
            data (dict): The data to process
            
        Returns:
            str: A generated task ID (UUID)
        """
        # Generate a unique ID to maintain similar interface
        task_id = str(uuid.uuid4())
        
        # Process data in the current thread
        result = self.process_sync(data)
        
        # Store result for potential retrieval by task_id
        # This implementation doesn't actually store it, but could be enhanced
        # with a simple cache or database storage if needed
        
        return task_id
        
    def process_sync(self, data):
        """Process XBRL data synchronously"""
        return process_xbrl_data(data)

class XBRLSimpleProcessor(XBRLProcessor):
    """Handles processing for simplified XBRL submissions"""
    pass

class XBRLFullProcessor(XBRLProcessor):
    """Handles processing for full XBRL submissions"""
    pass

def process_xbrl_data(data):
    """
    Process XBRL data synchronously
    
    Args:
        data (dict): The data to process
        
    Returns:
        dict: The processed data with mapping complete and filing ID if stored
    """
    try:
        logfire.info("Starting financial data mapping process")
        
        # Convert to JSON string for processing
        data_json = json.dumps(data, indent=4)
        logfire.debug("Input data prepared", data_size=len(data_json))
        
        # Call the financial statement agent directly
        logfire.info("Executing financial statement agent")
        result_mapping = financial_statement_agent.run_sync(
            f'Please map this financial statement data: {data_json}',
            deps=financial_deps
        )
        logfire.info("Financial statement agent completed successfully")
        
        # Convert result to dictionary
        logfire.debug("Processing agent results")
        if hasattr(result_mapping.data, 'model_dump'):  # Pydantic v2
            mapped_data_dict = result_mapping.data.model_dump()
        elif hasattr(result_mapping.data, 'dict'):      # Pydantic v1
            mapped_data_dict = result_mapping.data.dict()
        else:
            # Fallback to manual conversion
            mapped_data_dict = {k: v for k, v in result_mapping.data.__dict__.items() 
                            if not k.startswith('_')}
        
        logfire.info("Financial data mapping completed successfully")
        
        # Only proceed to database operations if mapped data was obtained
        if not mapped_data_dict:
            return {
                "success": False,
                "error": "No mapped data was produced",
                "mapped_data": None
            }
            
        # Store mapped data in database
        try:
            # Ensure Django is properly set up - this requires DJANGO_SETTINGS_MODULE to be set
            try:
                import os
                import django
                
                # Ensure settings module is properly set
                if not os.environ.get('DJANGO_SETTINGS_MODULE'):
                    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'XBRL.settings')
                    
                django.setup()
                
                # Import here to avoid circular imports AFTER Django is properly set up
                from .storage import store_mapped_data_to_db
                
                # Try accessing a model to verify Django setup worked
                from django.apps import apps
                app_models = apps.get_models()
                logfire.debug(f"Django initialized with {len(app_models)} models")
                
            except Exception as django_setup_error:
                logfire.error(f"Django setup failed: {str(django_setup_error)}")
                return {
                    "success": False,
                    "error": f"Django initialization error: {str(django_setup_error)}",
                    "mapped_data": mapped_data_dict
                }
            
            # Now proceed with storing the data
            filing_id = store_mapped_data_to_db(mapped_data_dict)
            logfire.info(f"Successfully stored mapped data in database with ID: {filing_id}")
            
            return {
                "success": True,
                "filing_id": str(filing_id),
                "mapped_data": mapped_data_dict
            }
        except AttributeError as attr_error:
            if "objects" in str(attr_error):
                error_msg = "Django model manager not available. This usually means Django wasn't properly initialized."
            else:
                error_msg = str(attr_error)
                
            logfire.exception(f"AttributeError during database operation: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "mapped_data": mapped_data_dict
            }
        except Exception as db_error:
            logfire.exception("Error storing mapped data in database", error=str(db_error))
            return {
                "success": False,
                "error": str(db_error),
                "mapped_data": mapped_data_dict
            }
            
    except Exception as e:
        error_type = type(e).__name__
        error_details = str(e)
        
        logfire.exception(
            "Error during financial data mapping", 
            error=error_details,
            error_type=error_type
        )
        
        return {
            "success": False,
            "error": error_details,
            "mapped_data": None
        }