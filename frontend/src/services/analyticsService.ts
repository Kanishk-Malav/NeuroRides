import { apiService } from './api';
import { DashboardData, KPI, ChartData, RideAnalytics, RevenueAnalytics, FleetAnalytics } from '../types';

class AnalyticsService {
  async getDashboardData(): Promise<DashboardData> {
    return apiService.get<DashboardData>('/analytics/dashboard/');
  }

  async getKPIs(): Promise<KPI[]> {
    return apiService.get<KPI[]>('/analytics/kpis/');
  }

  async getChartData(params: {
    metric_name: string;
    start_date: string;
    end_date: string;
    chart_type?: string;
    granularity?: string;
  }): Promise<ChartData> {
    return apiService.post<ChartData>('/analytics/charts/', params);
  }

  async getRideAnalytics(params?: {
    start_date?: string;
    end_date?: string;
    granularity?: string;
    city?: string;
  }): Promise<RideAnalytics[]> {
    return apiService.get<RideAnalytics[]>('/analytics/rides/', { params });
  }

  async getRevenueAnalytics(params?: {
    start_date?: string;
    end_date?: string;
    granularity?: string;
    city?: string;
  }): Promise<RevenueAnalytics[]> {
    return apiService.get<RevenueAnalytics[]>('/analytics/revenue/', { params });
  }

  async getFleetAnalytics(params?: {
    start_date?: string;
    end_date?: string;
    granularity?: string;
    city?: string;
  }): Promise<FleetAnalytics[]> {
    return apiService.get<FleetAnalytics[]>('/analytics/fleet/', { params });
  }

  async getPerformanceMetrics(params?: {
    service_name?: string;
    category?: string;
    hours_back?: number;
  }): Promise<any[]> {
    return apiService.get<any[]>('/analytics/performance/', { params });
  }

  async getServiceHealth(serviceName?: string): Promise<any> {
    const url = serviceName ? `/analytics/health/${serviceName}/` : '/analytics/health/';
    return apiService.get<any>(url);
  }

  async exportAnalyticsCSV(params: {
    start_date: string;
    end_date: string;
    metric_type: string;
  }): Promise<void> {
    return apiService.downloadFile('/analytics/export/csv/', 'analytics_export.csv');
  }

  async generateReport(templateId: string, params: {
    period_start: string;
    period_end: string;
    output_format: string;
    filters?: any;
  }): Promise<any> {
    return apiService.post<any>('/analytics/reports/generate/', {
      template_id: templateId,
      ...params
    });
  }

  async getReportTemplates(): Promise<any[]> {
    return apiService.get<any[]>('/analytics/reports/templates/');
  }

  async getGeneratedReports(): Promise<any[]> {
    return apiService.get<any[]>('/analytics/reports/');
  }

  async triggerDataAggregation(date?: string): Promise<any> {
    return apiService.post<any>('/analytics/admin/aggregate/', { date });
  }

  // Real-time analytics updates
  subscribeToAnalyticsUpdates(callback: (update: any) => void): () => void {
    // This would be implemented with WebSocket connection
    return () => {};
  }
}

export const analyticsService = new AnalyticsService();