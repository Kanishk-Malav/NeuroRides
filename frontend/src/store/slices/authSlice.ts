import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { User, LoginCredentials, RegisterData } from '../../types';
import axios from 'axios';

// Local RootState to avoid missing-module error for '../store'
type RootState = {
  auth: {
    user: any | null;
    isAuthenticated: boolean;
    loading: boolean;
    error: string | null;
  };
};

// --------------------------
// Auth State Interface
// --------------------------
interface AuthState {
  user: any | null;
  isAuthenticated: boolean;
  loading: boolean;     
  error: string | null;
}

// --------------------------
// Initial State
// --------------------------
const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  loading: false,       // <— MUST MATCH ABOVE
  error: null,
};

// --------------------------
// loginUser Thunk
// --------------------------
export const loginUser = createAsyncThunk<
  any,                                          // return type
  { email: string; password: string },          // payload type
  { rejectValue: string }                       // error type
>('auth/loginUser', async (payload, { rejectWithValue }) => {
  try {
    const response = await axios.post(
      `${process.env.REACT_APP_API_BASE_URL}/login/`,
      payload
    );

    return response.data;
  } catch (err: any) {
    return rejectWithValue(
      err.response?.data?.detail || 'Login failed.'
    );
  }
});

// --------------------------
// Slice
// --------------------------
const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout(state) {
      state.user = null;
      state.isAuthenticated = false;
    },
    clearAuthError(state) {
      state.error = null;
    },
  },

  extraReducers: (builder) => {
    // ----- LOGIN -----
    builder.addCase(loginUser.pending, (state) => {
      state.loading = true;          // <— CONSISTENT
      state.error = null;
    });

    builder.addCase(loginUser.fulfilled, (state, action) => {
      state.loading = false;
      state.isAuthenticated = true;
      state.user = action.payload.user;
    });

    builder.addCase(loginUser.rejected, (state, action) => {
      state.loading = false;
      state.isAuthenticated = false;
      state.error =
        (action.payload as string) ||
        action.error.message ||
        'Login failed';
    });
  },
});

export const { logout, clearAuthError } = authSlice.actions;
export default authSlice.reducer;

// Selector (optional)
export const selectAuth = (state: RootState) => state.auth;
