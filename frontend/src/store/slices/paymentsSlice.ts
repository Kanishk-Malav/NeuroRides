import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { PaymentsState, PaymentMethod, Payment } from '../../types';
import { paymentsService } from '../../services/paymentsService';

const initialState: PaymentsState = {
  paymentMethods: [],
  payments: [],
  isLoading: false,
  error: null,
};

// Async thunks
export const getPaymentMethods = createAsyncThunk(
  'payments/getPaymentMethods',
  async (_, { rejectWithValue }) => {
    try {
      const paymentMethods = await paymentsService.getPaymentMethods();
      return paymentMethods;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get payment methods');
    }
  }
);

export const addPaymentMethod = createAsyncThunk(
  'payments/addPaymentMethod',
  async (paymentMethodData: Partial<PaymentMethod>, { rejectWithValue }) => {
    try {
      const paymentMethod = await paymentsService.addPaymentMethod(paymentMethodData);
      return paymentMethod;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to add payment method');
    }
  }
);

export const getPaymentHistory = createAsyncThunk(
  'payments/getPaymentHistory',
  async (_, { rejectWithValue }) => {
    try {
      const payments = await paymentsService.getPaymentHistory();
      return payments;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to get payment history');
    }
  }
);

export const processPayment = createAsyncThunk(
  'payments/processPayment',
  async (paymentData: { rideId: string; paymentMethodId: string }, { rejectWithValue }) => {
    try {
      const payment = await paymentsService.processPayment(paymentData);
      return payment;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to process payment');
    }
  }
);

const paymentsSlice = createSlice({
  name: 'payments',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Get payment methods
      .addCase(getPaymentMethods.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(getPaymentMethods.fulfilled, (state, action) => {
        state.isLoading = false;
        state.paymentMethods = action.payload;
        state.error = null;
      })
      .addCase(getPaymentMethods.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Add payment method
      .addCase(addPaymentMethod.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(addPaymentMethod.fulfilled, (state, action) => {
        state.isLoading = false;
        state.paymentMethods.push(action.payload);
        state.error = null;
      })
      .addCase(addPaymentMethod.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get payment history
      .addCase(getPaymentHistory.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(getPaymentHistory.fulfilled, (state, action) => {
        state.isLoading = false;
        state.payments = action.payload;
      })
      .addCase(getPaymentHistory.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Process payment
      .addCase(processPayment.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(processPayment.fulfilled, (state, action) => {
        state.isLoading = false;
        state.payments.unshift(action.payload);
        state.error = null;
      })
      .addCase(processPayment.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = paymentsSlice.actions;
export default paymentsSlice.reducer;