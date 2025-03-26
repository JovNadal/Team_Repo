"""
XBRL Workflow Orchestrator

This module contains the orchestration logic for XBRL processing workflows,
coordinating between validation, mapping, storage, and tagging services.
"""
import uuid
import logfire
import datetime
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from django.db import close_old_connections, connection

from ..validators.mapping_validator import XBRLValidator
from ..processors.mapping import XBRLSimpleProcessor, XBRLFullProcessor
from ..processors.storage import map_pydantic_to_django_fields, store_mapped_data_to_db
from ...models import TaskStatus
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
    
    def get_task_status(self, task_id: str) -> WorkflowResult:
        """
        Get the status of a task by its ID
        
        Args:
            task_id: The unique identifier of the task
                
        Returns:
            WorkflowResult with the current status and relevant task information
            
        Raises:
            TaskStatus.DoesNotExist: Handled internally, returns 404 WorkflowResult
            Exception: Handled internally, returns 500 WorkflowResult with error details
        """
        try:
            task_status = TaskStatus.objects.get(id=task_id)
            
            # Base data included in all responses
            base_data = {
                "status": task_status.status,
                "created_at": task_status.created_at.isoformat(),
                "updated_at": task_status.updated_at.isoformat()
            }
            
            # Add status-specific response content
            if task_status.status == TaskStatus.COMPLETED:
                # Include filing_id for completed tasks
                if task_status.result_id:
                    base_data["filing_id"] = str(task_status.result_id)
                    
                return WorkflowResult(
                    success=True,
                    task_id=str(task_status.id),
                    message="Financial data mapping completed successfully",
                    data=base_data
                )
            elif task_status.status == TaskStatus.FAILED:
                return WorkflowResult(
                    success=False,
                    task_id=str(task_status.id),
                    message="Financial data mapping failed",
                    error=task_status.error_message,
                    data=base_data
                )
            else:
                # Task is still pending or processing
                return WorkflowResult(
                    success=True,
                    task_id=str(task_status.id),
                    message=f"Financial data mapping is {task_status.status}",
                    data=base_data
                )
        except TaskStatus.DoesNotExist:
            return WorkflowResult(
                success=False,
                task_id=task_id,
                message="Task not found",
                error="The specified task ID does not exist",
                status_code=404
            )
        except Exception as e:
            error_type = type(e).__name__
            error_details = str(e)
            
            logfire.exception(
                f"Error checking task status for ID: {task_id}",
                error=error_details,
                error_type=error_type
            )
            
            return WorkflowResult(
                success=False,
                task_id=task_id,
                message="Failed to check task status",
                error=error_details,
                status_code=500
            )        

    def process_financial_data(self, data: Dict[str, Any], use_fast_response: bool = True) -> WorkflowResult:
        """
        Process financial data through the complete workflow
        
        Args:
            data: The financial data to process
            use_fast_response: Whether to use the fast response pattern
            
        Returns:
            WorkflowResult containing task_id and status
        """
        # Generate a unique ID for this task
        task_id = str(uuid.uuid4())
        
        try:
            # Create a TaskStatus entry in the database
            task_status = TaskStatus.objects.create(
                id=uuid.UUID(task_id),
                status=TaskStatus.PENDING
            )
            
            logfire.info(f"Starting workflow for financial data processing with task_id: {task_id}")
            
            # Validate input data
            validation_result = self.validator.validate(data)
            
            if not validation_result.is_valid:
                logfire.warning(f"Validation failed for financial data", 
                               task_id=task_id, 
                               errors=validation_result.errors)
                
                # Update task status to failed
                task_status.status = TaskStatus.FAILED
                task_status.error_message = str(validation_result.errors)
                task_status.save()
                
                return WorkflowResult(
                    success=False,
                    task_id=task_id,
                    message="Financial data validation failed",
                    error=validation_result.errors,
                    status_code=400
                )
            
            # If using fast response pattern, return immediately with task ID
            if use_fast_response:
                # Update task status to processing
                task_status.status = TaskStatus.PROCESSING
                task_status.save()
                
                # Processing will continue asynchronously
                self._process_async(data, task_id)
                
                return WorkflowResult(
                    success=True,
                    task_id=task_id,
                    message="Financial data mapping request accepted for processing",
                    data={"status": TaskStatus.PROCESSING, "task_id": task_id},
                    status_code=202  # Accepted
                )
            else:
                # Process synchronously
                task_status.status = TaskStatus.PROCESSING
                task_status.save()
                
                result = self.simple_processor.process_sync(data)
                success = result.get('success', False)
                
                # Update task status based on result
                if success:
                    task_status.status = TaskStatus.COMPLETED
                    task_status.result_id = result.get('filing_id')
                    task_status.additional_data = {"filing_id": result.get('filing_id')}
                    task_status.save()
                else:
                    task_status.status = TaskStatus.FAILED
                    task_status.error_message = result.get('error', 'Unknown error')
                    task_status.save()
                
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
            
            # Try to update task status if it was created
            try:
                TaskStatus.objects.filter(id=uuid.UUID(task_id)).update(
                    status=TaskStatus.FAILED,
                    error_message=error_details
                )
            except Exception:
                pass  # Ignore errors in error handling
            
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
            success = result.get('success', False)
            filing_id = result.get('filing_id')
            
            # Update the TaskStatus record with the result
            try:
                task_status = TaskStatus.objects.get(id=uuid.UUID(task_id))
                
                # Generate ISO format timestamp
                current_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                if success:
                    task_status.status = TaskStatus.COMPLETED
                    task_status.result_id = uuid.UUID(filing_id) if filing_id else None
                    task_status.additional_data = {
                        "filing_id": filing_id,
                        "timestamp": current_timestamp
                    }
                else:
                    task_status.status = TaskStatus.FAILED
                    task_status.error_message = result.get('error', 'Unknown error')
                    task_status.additional_data = {
                        "error_details": result.get('error', 'Unknown error'),
                        "timestamp": current_timestamp
                    }
                
                task_status.save()
                
            except Exception as db_error:
                logfire.exception(
                    f"Error updating task status for task_id: {task_id}",
                    error=str(db_error)
                )
            
            # Log the outcome
            if success:
                logfire.info(f"Financial data mapping completed successfully for task_id: {task_id}",
                           filing_id=filing_id)
            else:
                logfire.error(f"Financial data mapping failed for task_id: {task_id}",
                            error=result.get('error', 'Unknown error'))
            
        except Exception as e:
            # Error handling for background processing
            error_type = type(e).__name__
            error_details = str(e)
            
            logfire.exception(
                f"Error during background processing for task_id: {task_id}", 
                error=error_details,
                error_type=error_type
            )
            
            # Update task status to failed
            try:
                # Generate ISO format timestamp for error case
                current_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                TaskStatus.objects.filter(id=uuid.UUID(task_id)).update(
                    status=TaskStatus.FAILED,
                    error_message=error_details,
                    additional_data={"error_timestamp": current_timestamp}
                )
            except Exception:
                pass  # Ignore errors in error handling
                
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
                
                # Create a task status record for this update
                TaskStatus.objects.create(
                    id=uuid.UUID(task_id),
                    status=TaskStatus.COMPLETED,
                    result_id=uuid.UUID(id),
                    additional_data={
                        "filing_id": id,
                        "uen": uen,
                        "operation": "update"
                    }
                )
                
                return WorkflowResult(
                    success=True,
                    task_id=task_id,
                    message=f"Financial data for UEN {uen} updated successfully",
                    data={
                        "filing_id": id,
                        "task_id": task_id,
                        "mapped_data": mapped_data
                    },
                    status_code=200
                )
                
            except Exception as db_error:
                logfire.exception("Error updating financial data in database", error=str(db_error))
                
                # Create a failed task status
                TaskStatus.objects.create(
                    id=uuid.UUID(task_id),
                    status=TaskStatus.FAILED,
                    error_message=str(db_error)
                )
                
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
            
            # Try to create a failed task status
            try:
                TaskStatus.objects.create(
                    id=uuid.UUID(task_id),
                    status=TaskStatus.FAILED,
                    error_message=error_details
                )
            except Exception:
                pass  # Ignore errors in error handling
            
            return WorkflowResult(
                success=False,
                task_id=task_id,
                message=f"Failed to update financial data for ID: {id}",
                error=error_details,
                status_code=500
            )