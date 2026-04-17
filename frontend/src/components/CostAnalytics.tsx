import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  DollarSign, 
  TrendingUp, 
  Zap, 
  BarChart3, 
  Calendar,
  Users,
  Clock
} from 'lucide-react';
import { projectsApi } from '../api/client';

interface CostAnalyticsProps {
  projectId: string;
  className?: string;
  projectStatus?: string; // Add project status to trigger refresh
}

interface CostAnalytics {
  project_id: string;
  project_name: string;
  total_runs: number;
  total_cost_usd: number;
  total_tokens: number;
  average_cost_per_run: number;
  cost_by_agent: { [key: string]: number };
  recent_runs: Array<{
    run_id: string;
    created_at: string;
    status: string;
    cost_usd: number;
    tokens: number;
  }>;
  cost_trend: Array<{
    run_id: string;
    created_at: string;
    status: string;
    cost_usd: number;
    tokens: number;
  }>;
}

const CostAnalytics: React.FC<CostAnalyticsProps> = ({ projectId, className = "", projectStatus }) => {
  const isActiveBuild =
    projectStatus === 'running' || projectStatus === 'waiting_review';

  const { data: analytics, isLoading, error, refetch } = useQuery<CostAnalytics>({
    queryKey: ['project-cost-analytics', projectId],
    queryFn: () => projectsApi.getCostAnalytics(projectId),
    enabled: !!projectId,
    refetchInterval: isActiveBuild ? 4000 : false,
    refetchOnWindowFocus: false,
    staleTime: isActiveBuild ? 0 : 30000,
    gcTime: 300000, // Keep in cache for 5 minutes
    retry: (failureCount, error: any) => {
      // Don't retry on auth errors or not found
      if (error?.response?.status === 401 || error?.response?.status === 403 || error?.response?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });

  // Refetch cost analytics when project completes
  useEffect(() => {
    if (projectStatus === 'completed' || projectStatus === 'failed') {
      console.log('🔄 Project completed/failed - refreshing cost analytics');
      // Wait a bit for the backend to finalize cost calculations
      setTimeout(() => {
        refetch();
      }, 2000);
    }
  }, [projectStatus, refetch]);

  if (isLoading) {
    return (
      <div className={`bg-gray-800 rounded-xl p-6 border border-gray-700 ${className}`}>
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="h-5 w-5 text-blue-400" />
          <h3 className="text-lg font-medium text-gray-200">Cost Analytics</h3>
        </div>
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="h-16 bg-gray-700 rounded"></div>
            <div className="h-16 bg-gray-700 rounded"></div>
          </div>
          <div className="h-32 bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  if (error || !analytics) {
    const axiosError = error as any;
    console.error('Cost analytics error:', error);
    return (
      <div className={`bg-gray-800 rounded-xl p-6 border border-gray-700 ${className}`}>
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="h-5 w-5 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-400">Cost Analytics</h3>
        </div>
        <p className="text-gray-500 text-sm">
          {axiosError?.response?.status === 401 || axiosError?.response?.status === 403 
            ? 'Authentication required to view cost analytics' 
            : axiosError?.response?.status === 404 
            ? 'Project not found' 
            : error 
            ? 'Failed to load cost analytics' 
            : 'No cost data available'}
        </p>
        {axiosError?.response?.status === 401 || axiosError?.response?.status === 403 ? (
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-xs text-indigo-400 hover:text-indigo-300"
          >
            Refresh page to re-authenticate
          </button>
        ) : null}
      </div>
    );
  }

  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTokens = (tokens: number) => tokens.toLocaleString();
  const formatDate = (dateStr: string) => new Date(dateStr).toLocaleDateString();

  // Calculate trend (last 5 runs vs previous 5)
  const recentRuns = analytics.cost_trend.slice(0, 5);
  const previousRuns = analytics.cost_trend.slice(5, 10);
  const recentAvg = recentRuns.reduce((sum, run) => sum + run.cost_usd, 0) / (recentRuns.length || 1);
  const previousAvg = previousRuns.reduce((sum, run) => sum + run.cost_usd, 0) / (previousRuns.length || 1);
  const trend = recentAvg > previousAvg ? 'up' : recentAvg < previousAvg ? 'down' : 'stable';
  const trendPercent = previousAvg > 0 ? Math.abs(((recentAvg - previousAvg) / previousAvg) * 100) : 0;

  return (
    <div className={`bg-gray-800 rounded-xl p-6 border border-gray-700 ${className}`}>
      <div className="flex items-center gap-2 mb-6">
        <BarChart3 className="h-5 w-5 text-blue-400" />
        <h3 className="text-lg font-medium text-gray-200">Cost Analytics</h3>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="h-4 w-4 text-green-400" />
            <span className="text-xs text-gray-400">Total Cost</span>
          </div>
          <div className="text-xl font-bold text-green-400">
            {formatCost(analytics.total_cost_usd)}
          </div>
        </div>

        <div className="bg-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-4 w-4 text-purple-400" />
            <span className="text-xs text-gray-400">Total Tokens</span>
          </div>
          <div className="text-xl font-bold text-purple-400">
            {formatTokens(analytics.total_tokens)}
          </div>
        </div>

        <div className="bg-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <Calendar className="h-4 w-4 text-blue-400" />
            <span className="text-xs text-gray-400">Total Runs</span>
          </div>
          <div className="text-xl font-bold text-blue-400">
            {analytics.total_runs}
          </div>
        </div>

        <div className="bg-gray-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className={`h-4 w-4 ${
              trend === 'up' ? 'text-red-400' : 
              trend === 'down' ? 'text-green-400' : 
              'text-gray-400'
            }`} />
            <span className="text-xs text-gray-400">Avg/Run</span>
          </div>
          <div className="text-xl font-bold text-white">
            {formatCost(analytics.average_cost_per_run)}
          </div>
          {trend !== 'stable' && (
            <div className={`text-xs ${
              trend === 'up' ? 'text-red-400' : 'text-green-400'
            }`}>
              {trend === 'up' ? '↑' : '↓'} {trendPercent.toFixed(1)}%
            </div>
          )}
        </div>
      </div>

      {/* Cost by Agent */}
      {Object.keys(analytics.cost_by_agent).length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-300 mb-3">Cost by Agent</h4>
          <div className="space-y-2">
            {Object.entries(analytics.cost_by_agent)
              .sort(([,a], [,b]) => b - a)
              .slice(0, 6) // Show top 6 agents
              .map(([agent, cost]) => {
                const percentage = (cost / analytics.total_cost_usd) * 100;
                return (
                  <div key={agent} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Users className="h-3 w-3 text-gray-400" />
                      <span className="text-sm text-gray-300">{agent}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-16 bg-gray-600 rounded-full h-2">
                        <div 
                          className="bg-blue-400 h-2 rounded-full" 
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <span className="text-sm text-green-400 min-w-[4rem] text-right">
                        {formatCost(cost)}
                      </span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Recent Runs */}
      {analytics.recent_runs.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-300 mb-3">Recent Runs</h4>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {analytics.recent_runs.map((run) => (
              <div key={run.run_id} className="flex items-center justify-between p-2 bg-gray-700 rounded text-sm">
                <div className="flex items-center gap-2">
                  <Clock className="h-3 w-3 text-gray-400" />
                  <span className="text-gray-300">{formatDate(run.created_at)}</span>
                  <span className={`px-2 py-1 rounded text-xs ${
                    run.status === 'completed' ? 'bg-green-900 text-green-300' :
                    run.status === 'failed' ? 'bg-red-900 text-red-300' :
                    'bg-yellow-900 text-yellow-300'
                  }`}>
                    {run.status}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-400 text-xs">
                    {formatTokens(run.tokens)} tokens
                  </span>
                  <span className="text-green-400 min-w-[3rem] text-right">
                    {formatCost(run.cost_usd)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {analytics.total_runs === 0 && (
        <div className="text-center py-8">
          <BarChart3 className="h-12 w-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">No runs yet</p>
          <p className="text-gray-600 text-sm">Cost analytics will appear after your first build</p>
        </div>
      )}
    </div>
  );
};

export default CostAnalytics;