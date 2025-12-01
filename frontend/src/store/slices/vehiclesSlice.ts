import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { VehiclesState, Vehicle } from '../../types';
import { vehiclesService } from '../../services/vehiclesService';

const initialState: VehiclesState = {
  vehicles: [],
  selectedVehicle: null,
  isLoading: false,
  error: null,
  loading: false
};

// Async thunks
export const getVehicles = createAsyncThunk(
  'vehicles/getVehicles',
  async (_, { rejectWithValue }) => {
    try {
      const vehicles = await vehiclesService.getVehicles();
      return vehicles;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get vehicles');
    }
  }
);

export const getVehicleById = createAsyncThunk(
  'vehicles/getVehicleById',
  async (vehicleId: string, { rejectWithValue }) => {
    try {
      const vehicle = await vehiclesService.getVehicleById(vehicleId);
      return vehicle;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get vehicle');
    }
  }
);

const vehiclesSlice = createSlice({
  name: 'vehicles',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setSelectedVehicle: (state, action: PayloadAction<Vehicle | null>) => {
      state.selectedVehicle = action.payload;
    },
    updateVehicleLocation: (state, action: PayloadAction<{ vehicleId: string; location: { latitude: number; longitude: number } }>) => {
      const { vehicleId, location } = action.payload;
      const vehicle = state.vehicles.find(v => v.id === vehicleId);
      if (vehicle) {
        vehicle.current_location = location;
      }
      if (state.selectedVehicle?.id === vehicleId) {
        state.selectedVehicle.current_location = location;
      }
    },
    updateVehicleStatus: (state, action: PayloadAction<{ vehicleId: string; status: Vehicle['status'] }>) => {
      const { vehicleId, status } = action.payload;
      const vehicle = state.vehicles.find(v => v.id === vehicleId);
      if (vehicle) {
        vehicle.status = status;
      }
      if (state.selectedVehicle?.id === vehicleId) {
        state.selectedVehicle.status = status;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Get vehicles
      .addCase(getVehicles.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(getVehicles.fulfilled, (state, action) => {
        state.isLoading = false;
        state.vehicles = action.payload;
        state.error = null;
      })
      .addCase(getVehicles.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get vehicle by ID
      .addCase(getVehicleById.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(getVehicleById.fulfilled, (state, action) => {
        state.isLoading = false;
        state.selectedVehicle = action.payload;
      })
      .addCase(getVehicleById.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError, setSelectedVehicle, updateVehicleLocation, updateVehicleStatus } = vehiclesSlice.actions;
export default vehiclesSlice.reducer;