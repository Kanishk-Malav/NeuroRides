// frontend/src/store/slices/analyticsSlice.ts

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

// CRA / Netlify env
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '';

if (!API_BASE_URL) {
  console.warn(
    'REACT_APP_API_BASE_URL is not set. Analytics API calls may fail.'
  );
}

// -------------------- Types --------------------

export interface AnalyticsState {
  dashboardData: any | null;
  kpis: any[];          // simple for now
  chartData: any;       // simple for now
  vehicles: any[];      // simple for now
  isLoading: boolean;
  error: string | null;
}

// -------------------- Thunks --------------------

// 📊 Dashboard analytics
export const fetchAnalytics = createAsyncThunk<
  any,
  void,
  { rejectValue: string }
>('analytics/fetchAnalytics', async (_payload, { rejectWithValue }) => {
  try {
    // TODO: yaha apna REAL endpoint daalna
    // Example:
    // const res = await axios.get(`${API_BASE_URL}/api/dashboard/analytics/`);
    const res = await axios.get(`${API_BASE_URL}/api/analytics/dashboard/`);
    return res.data;
  } catch (err: any) {
    if (axios.isAxiosError(err)) {
      const data: any = err.response?.data;
      const msg =
        data?.detail ||
        data?.error ||
        (typeof data === 'string' ? data : null) ||
        'Failed to load analytics';
      return rejectWithValue(msg);
    }
    return rejectWithValue('Failed to load analytics');
  }
});

// 🚗 Vehicles list
export const fetchVehicles = createAsyncThunk<
  any[],
  void,
  { rejectValue: string }
>('analytics/fetchVehicles', async (_payload, { rejectWithValue }) => {
  try {
    // TODO: yaha apna REAL vehicles endpoint daalna
    // Example:
    // const res = await axios.get(`${API_BASE_URL}/api/vehicles/`);
    const res = await axios.get(`${API_BASE_URL}/api/vehicles/`);

    const raw = (res.data?.results || res.data) as any[];
    return raw || [];
  } catch (err: any) {
    if (axios.isAxiosError(err)) {
      const data: any = err.response?.data;
      const msg =
        data?.detail ||
        data?.error ||
        (typeof data === 'string' ? data : null) ||
        'Failed to load vehicles';
      return rejectWithValue(msg);
    }
    return rejectWithValue('Failed to load vehicles');
  }
});

// -------------------- Initial state --------------------

const initialState: AnalyticsState = {
  dashboardData: null,
  kpis: [],
  chartData: {},
  vehicles: [],
  isLoading: false,
  error: null,
};

// -------------------- Slice --------------------

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    clearAnalyticsError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // ----- fetchAnalytics -----
    builder
      .addCase(fetchAnalytics.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchAnalytics.fulfilled, (state, action) => {
        state.isLoading = false;
        state.dashboardData = action.payload;

        // Agar backend kpis/charts bhej raha hai to yaha map kar sakte ho
        const payload: any = action.payload || {};
        if (Array.isArray(payload.kpis)) {
          state.kpis = payload.kpis;
        }
        if (payload.charts) {
          state.chartData = payload.charts;
        }
      })
      .addCase(fetchAnalytics.rejected, (state, action) => {
        state.isLoading = false;
        state.error =
          (action.payload as string) ||
          action.error.message ||
          'Failed to load analytics';
      });

    // ----- fetchVehicles -----
    builder
      .addCase(fetchVehicles.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchVehicles.fulfilled, (state, action) => {
        state.isLoading = false;
        state.vehicles = action.payload || [];
      })
      .addCase(fetchVehicles.rejected, (state, action) => {
        state.isLoading = false;
        state.error =
          (action.payload as string) ||
          action.error.message ||
          'Failed to load vehicles';
      });
  },
});

// -------------------- Exports --------------------

export const { clearAnalyticsError } = analyticsSlice.actions;
export default analyticsSlice.reducer;
