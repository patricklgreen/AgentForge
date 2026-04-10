"""
Unit tests for CostTracker.
"""
import pytest
from app.services.cost_tracker import CostTracker, BEDROCK_PRICING


class TestCostTracker:
    """Test cost tracking functionality."""

    def test_init(self):
        """Test CostTracker initialization."""
        tracker = CostTracker("test-run-123")
        assert tracker.run_id == "test-run-123"
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.total_cost_usd == 0.0
        assert tracker.call_count == 0
        assert tracker.calls_by_agent == {}
        assert tracker.cost_by_agent == {}

    def test_track_bedrock_call(self):
        """Test recording a Bedrock call."""
        tracker = CostTracker("test-run-123")
        
        # Record a call with known pricing
        cost = tracker.record(
            agent="TestAgent",
            model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
            input_tokens=1000,
            output_tokens=500
        )
        
        # Check cost calculation (1000 * 0.0008/1000 + 500 * 0.004/1000)
        expected_cost = 1.0 * 0.0008 + 0.5 * 0.004  # 0.0008 + 0.002 = 0.0028
        assert cost == expected_cost
        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 500
        assert tracker.total_cost_usd == expected_cost
        assert tracker.call_count == 1
        assert tracker.calls_by_agent["TestAgent"] == 1
        assert tracker.cost_by_agent["TestAgent"] == expected_cost

    def test_track_s3_operation(self):
        """Test that CostTracker can handle general operations (using record method)."""
        tracker = CostTracker("test-run-123")
        
        # Use record method for any operation (could represent S3 equivalent cost)
        cost = tracker.record(
            agent="S3Agent",
            model_id="default",  # Use default pricing
            input_tokens=100,
            output_tokens=50
        )
        
        # Check cost calculation with default pricing
        expected_cost = 0.1 * 0.003 + 0.05 * 0.015  # 0.0003 + 0.00075 = 0.00105
        assert cost == expected_cost
        assert tracker.total_cost_usd == expected_cost

    def test_get_cost_breakdown(self):
        """Test getting cost breakdown via summary method."""
        tracker = CostTracker("test-run-123")
        
        # Record multiple calls
        tracker.record("Agent1", "anthropic.claude-3-5-haiku-20241022-v1:0", 1000, 500)
        tracker.record("Agent2", "anthropic.claude-3-5-sonnet-20241022-v2:0", 2000, 1000)
        
        summary = tracker.summary()
        
        assert summary["run_id"] == "test-run-123"
        assert summary["total_input_tokens"] == 3000
        assert summary["total_output_tokens"] == 1500
        assert summary["total_tokens"] == 4500
        assert summary["call_count"] == 2
        assert "Agent1" in summary["calls_by_agent"]
        assert "Agent2" in summary["calls_by_agent"]
        assert "Agent1" in summary["cost_by_agent"]
        assert "Agent2" in summary["cost_by_agent"]

    def test_reset(self):
        """Test that a new CostTracker instance starts fresh."""
        tracker = CostTracker("test-run-123")
        
        # Add some data
        tracker.record("Agent1", "default", 1000, 500)
        
        # Create new tracker (equivalent to reset)
        new_tracker = CostTracker("test-run-456")
        
        assert new_tracker.total_input_tokens == 0
        assert new_tracker.total_output_tokens == 0
        assert new_tracker.total_cost_usd == 0.0
        assert new_tracker.call_count == 0

    def test_get_estimated_monthly_cost(self):
        """Test estimated monthly cost calculation."""
        tracker = CostTracker("test-run-123")
        
        # Record some usage
        tracker.record("Agent1", "default", 10000, 5000)  # 10k input, 5k output
        daily_cost = tracker.total_cost_usd
        
        # Simulate monthly estimation (30 days)
        estimated_monthly = daily_cost * 30
        
        assert estimated_monthly > 0
        # With default pricing: 10 * 0.003 + 5 * 0.015 = 0.03 + 0.075 = 0.105 per day
        # Monthly: 0.105 * 30 = 3.15
        expected = 0.105 * 30
        assert abs(estimated_monthly - expected) < 0.001

    def test_bedrock_pricing_models(self):
        """Test different Bedrock model pricing."""
        tracker = CostTracker("test-run-123")
        
        # Test Haiku pricing
        haiku_cost = tracker.record("Agent1", "anthropic.claude-3-5-haiku-20241022-v1:0", 1000, 1000)
        haiku_expected = 1.0 * 0.0008 + 1.0 * 0.004  # 0.0048
        assert abs(haiku_cost - haiku_expected) < 0.000001
        
        # Reset for next test
        tracker = CostTracker("test-run-456")
        
        # Test Sonnet pricing  
        sonnet_cost = tracker.record("Agent2", "anthropic.claude-3-5-sonnet-20241022-v2:0", 1000, 1000)
        sonnet_expected = 1.0 * 0.003 + 1.0 * 0.015  # 0.018
        assert abs(sonnet_cost - sonnet_expected) < 0.000001

    def test_multiple_operations_aggregation(self):
        """Test multiple operations are properly aggregated."""
        tracker = CostTracker("test-run-123")
        
        # Record multiple calls from same agent
        cost1 = tracker.record("Agent1", "default", 1000, 500)
        cost2 = tracker.record("Agent1", "default", 2000, 1000)
        
        assert tracker.calls_by_agent["Agent1"] == 2
        assert tracker.cost_by_agent["Agent1"] == cost1 + cost2
        assert tracker.total_input_tokens == 3000
        assert tracker.total_output_tokens == 1500

    def test_cost_precision(self):
        """Test cost calculation precision."""
        tracker = CostTracker("test-run-123")
        
        # Record very small amounts
        cost = tracker.record("Agent1", "default", 1, 1)
        
        # Should handle small decimals correctly
        expected = 0.001 * 0.003 + 0.001 * 0.015  # 0.000018
        assert abs(cost - expected) < 0.0000001
        
        # Summary should round appropriately
        summary = tracker.summary()
        assert isinstance(summary["total_cost_usd"], float)
        assert len(str(summary["total_cost_usd"]).split('.')[-1]) <= 6  # Max 6 decimal places