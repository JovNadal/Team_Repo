from django.shortcuts import render
from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import asyncio
import logfire

logfire.configure(console=False, inspect_arguments=False)
logfire.instrument_openai()

# Import the necessary dependencies
from .services.agent import xbrl_tagging_agent
from .services.dependencies import sg_xbrl_deps

# View for handling XBRL tagging
@api_view(['POST'])
def tag_financial_data(request):
    """Apply XBRL tags to already mapped financial data"""
    try:
        logfire.info("Starting XBRL tagging process")
        
        # Extract data from request
        data = request.data.get('data', {})
        
        # Convert to JSON string for processing
        data_json = json.dumps(data, indent=4)
        logfire.debug("Input data prepared for tagging", data_size=len(data_json))
        
        # Use asyncio to run the async function in a sync view
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run the XBRL tagging agent
            logfire.info("Executing XBRL tagging agent")
            tagged_result = loop.run_until_complete(
                xbrl_tagging_agent.run(
                    f'Please apply appropriate XBRL tags to this financial data: {data_json}',
                    deps=sg_xbrl_deps
                )
            )
            logfire.info("XBRL tagging agent completed successfully")
        except Exception as e:
            logfire.exception("Error during XBRL tagging agent execution", error=str(e))
            raise
        finally:
            loop.close()
        
        # Log successful completion
        logfire.info("XBRL tagging completed successfully", 
                    tags_count=len(tagged_result.data.get_all_tags()))
        
        # Convert tagged data to dictionary
        if hasattr(tagged_result.data, 'model_dump'):  # Pydantic v2
            tagged_data_dict = tagged_result.data.model_dump()
        elif hasattr(tagged_result.data, 'dict'):      # Pydantic v1
            tagged_data_dict = tagged_result.data.dict()
        else:
            # Fallback to manual conversion
            tagged_data_dict = {k: v for k, v in tagged_result.data.__dict__.items() 
                               if not k.startswith('_')}
        
        # Return successful response
        return Response({
            "tagged_data": tagged_data_dict,
            "tags": tagged_result.data.get_all_tags()
        })
        
    except Exception as e:
        # Enhanced error logging
        error_type = type(e).__name__
        error_details = str(e)
        
        logfire.exception(
            "Error during XBRL tagging", 
            error=error_details,
            error_type=error_type
        )
        
        # Return error response
        return Response(
            {"error": f"Tagging error: {error_details}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )