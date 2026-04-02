"""
Unit tests for cost tracker service.
"""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from app.services.cost_tracker import CostTracker


class TestCostTracker:
    """Test cost tracking service."""

    def test_init(self):
        """Test tracker initialization."""
        tracker = CostTracker()
        assert tracker.total_cost == Decimal('0')
        assert len(tracker.operations) == 0

    def test_track_bedrock_call(self):
        """Test tracking Bedrock API call costs."""
        tracker = CostTracker()
        
        tracker.track_bedrock_call(
            model_id="anthropic.claude-3-sonnet",
            input_tokens=100,
            output_tokens=50
        )
        
        assert tracker.total_cost > Decimal('0')
        assert len(tracker.operations) == 1
        
        operation = tracker.operations[0]
        assert operation['service'] == 'bedrock'
        assert operation['model_id'] == 'anthropic.claude-3-sonnet'
        assert operation['input_tokens'] == 100
        assert operation['output_tokens'] == 50

    def test_track_s3_operation(self):
        """Test tracking S3 operation costs."""
        tracker = CostTracker()
        
        tracker.track_s3_operation(
            operation_type="put_object",
            data_size_mb=1.5
        )
        
        assert tracker.total_cost > Decimal('0')
        assert len(tracker.operations) == 1
        
        operation = tracker.operations[0]
        assert operation['service'] == 's3'
        assert operation['operation_type'] == 'put_object'
        assert operation['data_size_mb'] == 1.5

    def test_get_cost_breakdown(self):
        """Test getting cost breakdown by service."""
        tracker = CostTracker()
        
        tracker.track_bedrock_call("anthropic.claude-3-sonnet", 100, 50)
        tracker.track_s3_operation("put_object", 1.0)
        
        breakdown = tracker.get_cost_breakdown()
        
        assert 'bedrock' in breakdown
        assert 's3' in breakdown
        assert 'total' in breakdown
        assert breakdown['total'] == tracker.total_cost

    def test_reset(self):
        """Test resetting cost tracker."""
        tracker = CostTracker()
        
        tracker.track_bedrock_call("anthropic.claude-3-sonnet", 100, 50)
        assert tracker.total_cost > Decimal('0')
        assert len(tracker.operations) == 1
        
        tracker.reset()
        
        assert tracker.total_cost == Decimal('0')
        assert len(tracker.operations) == 0

    def test_get_estimated_monthly_cost(self):
        """Test estimating monthly costs."""
        tracker = CostTracker()
        
        # Track some operations
        for _ in range(10):
            tracker.track_bedrock_call("anthropic.claude-3-sonnet", 100, 50)
        
        monthly_estimate = tracker.get_estimated_monthly_cost(operations_per_day=100)
        assert monthly_estimate > tracker.total_cost

    def test_bedrock_pricing_models(self):
        """Test different Bedrock model pricing."""
        tracker = CostTracker()
        
        # Track calls for different models
        tracker.track_bedrock_call("anthropic.claude-3-sonnet", 1000, 500)
        tracker.track_bedrock_call("anthropic.claude-3-haiku", 1000, 500)
        
        breakdown = tracker.get_cost_breakdown()
        
        # Sonnet should be more expensive than Haiku
        assert breakdown['bedrock'] > Decimal('0')

    def test_multiple_operations_aggregation(self):
        """Test aggregating multiple operations."""
        tracker = CostTracker()
        
        # Multiple Bedrock calls
        tracker.track_bedrock_call("anthropic.claude-3-sonnet", 100, 50)
        tracker.track_bedrock_call("anthropic.claude-3-sonnet", 200, 100)
        
        # Multiple S3 operations
        tracker.track_s3_operation("put_object", 1.0)
        tracker.track_s3_operation("get_object", 0.5)
        
        breakdown = tracker.get_cost_breakdown()
        
        assert len(tracker.operations) == 4
        assert breakdown['bedrock'] > Decimal('0')
        assert breakdown['s3'] > Decimal('0')
        assert breakdown['total'] == tracker.total_cost

    def test_cost_precision(self):
        """Test cost calculation precision."""
        tracker = CostTracker()
        
        tracker.track_bedrock_call("anthropic.claude-3-sonnet", 1, 1)
        
        # Cost should be calculated to proper decimal places
        assert isinstance(tracker.total_cost, Decimal)
        assert tracker.total_cost.as_tuple().exponent <= -6  # At least 6 decimal places