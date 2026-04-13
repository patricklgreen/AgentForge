import React from 'react';
import { DollarSign, Zap, Clock, TrendingUp } from 'lucide-react';

interface CostSummary {
  run_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  call_count: number;
  calls_by_agent: { [key: string]: number };
  cost_by_agent: { [key: string]: number };
  note?: string;
}

interface CostTrackerProps {
  costSummary: CostSummary | null;
  isLoading?: boolean;
  className?: string;
}

export const CostTracker: React.FC<CostTrackerProps> = ({ 
  costSummary, 
  isLoading = false, 
  className = "" 
}) => {
  if (isLoading) {
    return (
      <div className={`bg-gray-800 rounded-lg p-4 border border-gray-700 ${className}`}>
        <div className="flex items-center gap-2 mb-3">
          <DollarSign className="h-4 w-4 text-green-400" />
          <h3 className="text-sm font-medium text-gray-200">Cost Tracking</h3>
        </div>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-700 rounded w-24 mb-2"></div>
          <div className="h-3 bg-gray-700 rounded w-32"></div>
        </div>
      </div>
    );
  }

  if (!costSummary || costSummary.total_cost_usd === 0) {
    return (
      <div className={`bg-gray-800 rounded-lg p-4 border border-gray-700 ${className}`}>
        <div className="flex items-center gap-2 mb-2">
          <DollarSign className="h-4 w-4 text-gray-500" />
          <h3 className="text-sm font-medium text-gray-400">Cost Tracking</h3>
        </div>
        <p className="text-xs text-gray-500">
          {costSummary?.note || "No cost data available"}
        </p>
      </div>
    );
  }

  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTokens = (tokens: number) => tokens.toLocaleString();

  return (
    <div className={`bg-gray-800 rounded-lg p-4 border border-gray-700 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <DollarSign className="h-4 w-4 text-green-400" />
        <h3 className="text-sm font-medium text-gray-200">Cost Tracking</h3>
      </div>

      {/* Main Cost Display */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-lg font-bold text-green-400">
            {formatCost(costSummary.total_cost_usd)}
          </div>
          <div className="text-xs text-gray-500">Total Cost</div>
        </div>
        <div>
          <div className="text-lg font-bold text-blue-400">
            {formatTokens(costSummary.total_tokens)}
          </div>
          <div className="text-xs text-gray-500">Total Tokens</div>
        </div>
      </div>

      {/* Token Breakdown */}
      <div className="grid grid-cols-2 gap-3 mb-3 text-xs">
        <div className="flex items-center gap-1">
          <TrendingUp className="h-3 w-3 text-orange-400" />
          <span className="text-gray-400">Input:</span>
          <span className="text-white">{formatTokens(costSummary.total_input_tokens)}</span>
        </div>
        <div className="flex items-center gap-1">
          <Zap className="h-3 w-3 text-purple-400" />
          <span className="text-gray-400">Output:</span>
          <span className="text-white">{formatTokens(costSummary.total_output_tokens)}</span>
        </div>
      </div>

      {/* LLM Calls */}
      <div className="flex items-center gap-1 mb-3 text-xs">
        <Clock className="h-3 w-3 text-gray-400" />
        <span className="text-gray-400">LLM Calls:</span>
        <span className="text-white">{costSummary.call_count}</span>
      </div>

      {/* Agent Breakdown */}
      {Object.keys(costSummary.cost_by_agent).length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">Cost by Agent</h4>
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {Object.entries(costSummary.cost_by_agent)
              .sort(([,a], [,b]) => b - a) // Sort by cost descending
              .map(([agent, cost]) => (
                <div key={agent} className="flex justify-between items-center text-xs">
                  <span className="text-gray-300 truncate">{agent}</span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-green-400">{formatCost(cost)}</span>
                    <span className="text-gray-500 text-[10px]">
                      ({costSummary.calls_by_agent[agent]} calls)
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CostTracker;