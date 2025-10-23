import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { RidesState, Ride, RideRequest } from '../../types';
import { ridesService } from '../../services/ridesService';

const initialState: RidesState = {
  currentRide: null,
  rideHistory: [],
  rides: [],
  fareEstimate: null,
  isLoading: false,
  loading: false,
  error: null,
};

// Async thunks
export const createRide = createAsyncThunk(
  'rides/createRide',
  async (rideRequest: RideRequest, { rejectWithValue }) => {
    try {
      const ride = await ridesService.createRide(rideRequest);
      return ride;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to create ride');
    }
  }
);

export const getCurrentRide = createAsyncThunk(
  'rides/getCurrentRide',
  async (_, { rejectWithValue }) => {
    try {
      const ride = await ridesService.getCurrentRide();
      return ride;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get current ride');
    }
  }
);

export const getRideHistory = createAsyncThunk(
  'rides/getRideHistory',
  async (_, { rejectWithValue }) => {
    try {
      const rides = await ridesService.getRideHistory();
      return rides;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get ride history');
    }
  }
);

export const fetchUserRides = createAsyncThunk(
  'rides/fetchUserRides',
  async (_, { rejectWithValue }) => {
    try {
      const rides = await ridesService.getRideHistory();
      return rides;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch user rides');
    }
  }
);

export const estimateFare = createAsyncThunk(
  'rides/estimateFare',
  async (fareRequest: any, { rejectWithValue }) => {
    try {
      const estimate = await ridesService.estimateFare(fareRequest);
      return estimate;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to estimate fare');
    }
  }
);

export const cancelRide = createAsyncThunk(
  'rides/cancelRide',
  async (rideId: string, { rejectWithValue }) => {
    try {
      const ride = await ridesService.cancelRide(rideId);
      return ride;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to cancel ride');
    }
  }
);

const ridesSlice = createSlice({
  name: 'rides',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    updateCurrentRide: (state, action: PayloadAction<Ride>) => {
      state.currentRide = action.payload;
    },
    clearCurrentRide: (state) => {
      state.currentRide = null;
    },
    addRideToHistory: (state, action: PayloadAction<Ride>) => {
      state.rideHistory.unshift(action.payload);
    },
    updateRideStatus: (state, action: PayloadAction<any>) => {
      if (state.currentRide && state.currentRide.id === action.payload.ride_id) {
        state.currentRide = { ...state.currentRide, ...action.payload };
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Create ride
      .addCase(createRide.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createRide.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentRide = action.payload;
        state.error = null;
      })
      .addCase(createRide.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get current ride
      .addCase(getCurrentRide.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(getCurrentRide.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentRide = action.payload;
      })
      .addCase(getCurrentRide.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get ride history
      .addCase(getRideHistory.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(getRideHistory.fulfilled, (state, action) => {
        state.isLoading = false;
        state.rideHistory = action.payload;
      })
      .addCase(getRideHistory.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Cancel ride
      .addCase(cancelRide.fulfilled, (state, action) => {
        state.currentRide = action.payload;
        // Update in history if exists
        const index = state.rideHistory.findIndex(ride => ride.id === action.payload.id);
        if (index !== -1) {
          state.rideHistory[index] = action.payload;
        }
      })
      // Fetch user rides
      .addCase(fetchUserRides.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchUserRides.fulfilled, (state, action) => {
        state.loading = false;
        state.rides = action.payload;
        state.rideHistory = action.payload;
      })
      .addCase(fetchUserRides.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Estimate fare
      .addCase(estimateFare.fulfilled, (state, action) => {
        state.fareEstimate = action.payload;
      });
  },
});

export const { clearError, updateCurrentRide, clearCurrentRide, addRideToHistory, updateRideStatus } = ridesSlice.actions;
export default ridesSlice.reducer;