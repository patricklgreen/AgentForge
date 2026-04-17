import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DollarSign, Zap, Calculator } from 'lucide-react';
import { projectsApi } from '../api/client';

interface CostTrackerProps {
  projectId: string;
  projectStatus?: string;
  className?: string;
}

const CostTracker: React.FC<CostTrackerProps> = ({ 
  projectId, 
  projectStatus,
  className = "" 
}) => {
  const isActiveBuild =
    projectStatus === 'running' || projectStatus === 'waiting_review';

  const { data: analytics, isLoading, error, refetch } = useQuery<any>({
    queryKey: ['project-cost-tracker', projectId],
    queryFn: () => projectsApi.getCostAnalytics(projectId),
    enabled: !!projectId,
    refetchInterval: isActiveBuild ? 4000 : false,
    refetchOnWindowFocus: false,
    staleTime: isActiveBuild ? 0 : 30000,
    gcTime: 300000, // 5 minutes
    retry: (failureCount, error: any) => {
      // Don't retry on 404 (project not found) or 403 (access denied)
      if (error?.response?.status === 404 || error?.response?.status === 403) {
        return false;
      }
      return failureCount < 3;
    },
  });

  // Refetch when project completes
  useEffect(() => {
    if (projectStatus === 'completed' || projectStatus === 'failed') {
      setTimeout(() => {
        refetch();
      }, 2000);
    }
  }, [projectStatus, refetch]);

  // Don't show anything while loading initially or if there's an error
  if (isLoading && !analytics) return null;
  if (error) {
    console.error('Cost tracker error:', error);
    return null;
  }
  if (!analytics || analytics.total_runs === 0) return null;

  const formatCost = (cost: number) => `$${cost.toFixed(4)}`;
  const formatTokens = (tokens: number) => tokens.toLocaleString();

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      {/* Total Cost */}
      <div className="flex items-center gap-1.5 text-sm">
        <DollarSign className="h-4 w-4 text-green-400" />
        <span className="text-gray-400">Cost:</span>
        <span className="text-green-400 font-medium">
          {formatCost(analytics.total_cost_usd)}
        </span>
      </div>

      {/* Total Tokens */}
      <div className="flex items-center gap-1.5 text-sm">
        <Zap className="h-4 w-4 text-purple-400" />
        <span className="text-gray-400">Tokens:</span>
        <span className="text-purple-400 font-medium">
          {formatTokens(analytics.total_tokens)}
        </span>
      </div>

      {/* Runs Count */}
      <div className="flex items-center gap-1.5 text-sm">
        <Calculator className="h-4 w-4 text-blue-400" />
        <span className="text-gray-400">Runs:</span>
        <span className="text-blue-400 font-medium">
          {analytics.total_runs}
        </span>
      </div>
    </div>
  );
};

export default CostTracker;