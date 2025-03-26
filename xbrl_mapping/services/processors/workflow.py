"""
XBRL Workflow Orchestrator

This module contains the orchestration logic for XBRL processing workflows,
coordinating between validation, mapping, storage, and tagging services.
"""
import uuid
import logfire
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from django.db import close_old_connections, connection

from ..validators.mapping_validator import XBRLValidator
from ..processors.mapping import XBRLSimpleProcessor, XBRLFullProcessor
from ..processors.storage import map_pydantic_to_django_fields, store_mapped_data_to_db
from ...utils.response import success_response, error_response


@dataclass
class WorkflowResult:
    """Result of a workflow execution"""
    success: bool
    task_id: str
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int = 200


class XBRLWorkflowOrchestrator:
    """
    Orchestrates the entire XBRL processing workflow, coordinating between
    validation, mapping, processing, and storage services.
    """
    
    def __init__(self):
        self.validator = XBRLValidator()
        self.simple_processor = XBRLSimpleProcessor()
        self.full_processor = XBRLFullProcessor()
        
    def process_financial_data(self, data: Dict[str, Any], use_fast_response: bool = True) -> WorkflowResult:
        """
        Process financial data through the complete workflow
        
        Args:
            data: The financial data to process
            use_fast_response: Whether to use the fast response pattern
            
        Returns:
            WorkflowResult containing task_id and status
        """
        task_id = str(uuid.uuid4())
        
        try:
            logfire.info(f"Starting workflow for financial data processing with task_id: {task_id}")
            
            # Validate input data
            validation_result = self.validator.validate(data)
            
            if not validation_result.is_valid:
                logfire.warning(f"Validation failed for financial data", 
                               task_id=task_id, 
                               errors=validation_result.errors)
                
                return WorkflowResult(
                    success=False,
                    task_id=task_id,
                    message="Financial data validation failed",
                    error=validation_result.errors,
                    status_code=400
                )
            
            # If using fast response pattern, return immediately with task ID
            if use_fast_response:
                # Processing will continue asynchronously
                self._process_async(data, task_id)
                
                return WorkflowResult(
                    success=True,
                    task_id=task_id,
                    message="Financial data mapping request accepted for processing",
                    data={"status": "processing", "task_id": task_id},
                    status_code=202  # Accepted
                )
            else:
                # Process synchronously
                result = self.simple_processor.process_sync(data)
                success = result.get('success', False)
                
                return WorkflowResult(
                    success=success,
                    task_id=task_id,
                    message="Financial data processed" if success else "Processing failed",
                    data=result,
                    error=result.get('error') if not success else None,
                    status_code=200 if success else 500
                )
                
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            
            logfire.exception(
                f"Error in workflow orchestration", 
                task_id=task_id,
                error=error_details,
                error_type=error_type
            )
            
            return WorkflowResult(
                success=False,
                task_id=task_id,
                message="Failed to process financial data",
                error=error_details,
                status_code=500
            )
    
    def _process_async(self, data: Dict[str, Any], task_id: str) -> None:
        """
        Start asynchronous processing of data in a separate thread
        
        Args:
            data: The data to process
            task_id: The task ID for tracking
        """
        from threading import Thread
        
        Thread(
            target=self._background_processing_task,
            args=(data, task_id),
            daemon=True
        ).start()
    
    def _background_processing_task(self, data: Dict[str, Any], task_id: str) -> None:
        """
        Background task for processing data after response is sent
        
        Args:
            data: The data to process
            task_id: The task ID for tracking
        """
        try:
            # Close any DB connections from the request cycle
            close_old_connections()
            
            logfire.info(f"Background processing started for task_id: {task_id}")
            
            # Process the data
            result = self.simple_processor.process_sync(data)
            
            # Log the outcome
            if result.get('success', False):
                logfire.info(f"Financial data mapping completed successfully for task_id: {task_id}",
                           filing_id=result.get('filing_id', None))
            else:
                logfire.error(f"Financial data mapping failed for task_id: {task_id}",
                            error=result.get('error', 'Unknown error'))
            
            # Here you could store the result in a persistent store (Redis, database, etc.)
            # for future status queries
            
        except Exception as e:
            # Error handling for background processing
            error_type = type(e).__name__
            error_details = str(e)
            
            logfire.exception(
                f"Error during background processing for task_id: {task_id}", 
                error=error_details,
                error_type=error_type
            )
        finally:
            # Always close connections when thread is done
            close_old_connections()
            if connection.connection:
                connection.close()
    
    def update_mapped_data(self, id: str, mapped_data: Dict[str, Any]) -> WorkflowResult:
        """
        Update existing mapped financial data
        
        Args:
            id: The UUID of the XBRL filing to update
            mapped_data: The new mapped data
            
        Returns:
            WorkflowResult with update status
        """
        from ...models import PartialXBRL
        from django.db import transaction
        
        task_id = str(uuid.uuid4())
        
        try:
            logfire.info(f"Starting financial data manual update for ID: {id}, task_id: {task_id}")
            
            # Check if the XBRL filing exists using UUID
            try:
                xbrl = PartialXBRL.objects.get(id=id)
                # Store the UEN for later use in responses
                uen = xbrl.filing_information.unique_entity_number
            except PartialXBRL.DoesNotExist:
                return WorkflowResult(
                    success=False,
                    task_id=task_id,
                    message=f"No XBRL filing found with ID: {id}",
                    status_code=404
                )
            
            if not mapped_data:
                return WorkflowResult(
                    success=False,
                    task_id=task_id,
                    message="Missing mapped data in request",
                    status_code=400
                )
            
            # Process the manually mapped data
            try:
                from ..processors.update import process_update_data
                
                # Process the update
                update_result = process_update_data(xbrl, mapped_data)
                
                if not update_result['success']:
                    return WorkflowResult(
                        success=False,
                        task_id=task_id,
                        message=update_result['message'],
                        error=update_result['error'],
                        status_code=400
                    )
                
                return WorkflowResult(
                    success=True,
                    task_id=task_id,
                    message=f"Financial data for UEN {uen} updated successfully",
                    data={
                        "filing_id": str(xbrl.id),
                        "mapped_data": mapped_data
                    },
                    status_code=200
                )
                
            except Exception as db_error:
                logfire.exception("Error updating financial data in database", error=str(db_error))
                return WorkflowResult(
                    success=False,
                    task_id=task_id,
                    message=f"Financial data could not be updated in the database for ID: {id}",
                    error=str(db_error),
                    data={"mapped_data": mapped_data},
                    status_code=500
                )
                
        except Exception as e:
            # Enhanced error logging with more details
            error_type = type(e).__name__
            error_details = str(e)
            
            logfire.exception(
                f"Error during financial data update for ID: {id}", 
                error=error_details,
                error_type=error_type
            )
            
            return WorkflowResult(
                success=False,
                task_id=task_id,
                message=f"Failed to update financial data for ID: {id}",
                error=error_details,
                status_code=500
            )