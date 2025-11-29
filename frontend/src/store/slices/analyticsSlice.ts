import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { AnalyticsState, DashboardData, KPI, ChartData } from '../../types';
import { analyticsService } from '../../services/analyticsService';

const initialState: AnalyticsState = {
  dashboardData: null,
  kpis: [],
  chartData: {},
  isLoading: false,
  error: null,
  analytics: undefined,
  loading: false
};

// Async thunks
export const getDashboardData = createAsyncThunk(
  'analytics/getDashboardData',
  async (_, { rejectWithValue }) => {
    try {
      const data = await analyticsService.getDashboardData();
      return data;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get dashboard data');
    }
  }
);

export const getKPIs = createAsyncThunk(
  'analytics/getKPIs',
  async (_, { rejectWithValue }) => {
    try {
      const kpis = await analyticsService.getKPIs();
      return kpis;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get KPIs');
    }
  }
);

export const getChartData = createAsyncThunk(
  'analytics/getChartData',
  async (params: { metric_name: string; start_date: string; end_date: string; chart_type?: string }, { rejectWithValue }) => {
    try {
      const chartData = await analyticsService.getChartData(params);
      return { key: params.metric_name, data: chartData };
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get chart data');
    }
  }
);

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setChartData: (state, action: PayloadAction<{ key: string; data: ChartData }>) => {
      const { key, data } = action.payload;
      state.chartData[key] = data;
    },
    clearChartData: (state) => {
      state.chartData = {};
    },
  },
  extraReducers: (builder) => {
    builder
      // Get dashboard data
      .addCase(getDashboardData.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(getDashboardData.fulfilled, (state, action) => {
        state.isLoading = false;
        state.dashboardData = action.payload;
        state.error = null;
      })
      .addCase(getDashboardData.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get KPIs
      .addCase(getKPIs.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(getKPIs.fulfilled, (state, action) => {
        state.isLoading = false;
        state.kpis = action.payload;
      })
      .addCase(getKPIs.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get chart data
      .addCase(getChartData.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(getChartData.fulfilled, (state, action) => {
        state.isLoading = false;
        const { key, data } = action.payload;
        state.chartData[key] = data;
      })
      .addCase(getChartData.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError, setChartData, clearChartData } = analyticsSlice.actions;
export default analyticsSlice.reducer;