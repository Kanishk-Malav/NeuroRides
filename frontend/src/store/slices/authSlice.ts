import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import axios from 'axios';
import { User, LoginCredentials, RegisterData, AuthState } from '../../types';

// --------------------------
// Initial State
// --------------------------
const initialState: AuthState = {
  user: null,
  token: localStorage.getItem('token'),
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

// --------------------------
// API Configuration
// --------------------------
const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || 'https://neurorides.onrender.com';

// --------------------------
// Thunks
// --------------------------

export const loginUser = createAsyncThunk<
  { user: User; access: string; refresh: string }, // Return type
  LoginCredentials, // Payload type
  { rejectValue: string } // Error type
>(
  'auth/loginUser',
  async (credentials, { rejectWithValue }) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/accounts/auth/login/`,
        credentials
      );
      
      // Store token in localStorage
      if (response.data.access) {
        localStorage.setItem('token', response.data.access);
        localStorage.setItem('refresh_token', response.data.refresh);
      }
      
      return response.data;
    } catch (err: any) {
      console.error('Login error:', err);
      return rejectWithValue(
        err.response?.data?.detail || 
        err.response?.data?.error || 
        'Login failed. Please check your credentials.'
      );
    }
  }
);

export const registerUser = createAsyncThunk<
  { user: User; tokens: { access: string; refresh: string } },
  RegisterData,
  { rejectValue: string }
>(
  'auth/registerUser',
  async (data, { rejectWithValue }) => {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/accounts/auth/register/`,
        data
      );
      
      if (response.data.tokens?.access) {
        localStorage.setItem('token', response.data.tokens.access);
        localStorage.setItem('refresh_token', response.data.tokens.refresh);
      }
      
      return response.data;
    } catch (err: any) {
      console.error('Registration error:', err);
      // Handle Django validation errors which might be an object
      if (err.response?.data && typeof err.response.data === 'object') {
        const errors = Object.values(err.response.data).flat();
        return rejectWithValue(errors[0] as string || 'Registration failed.');
      }
      return rejectWithValue('Registration failed. Please try again.');
    }
  }
);

export const logoutUser = createAsyncThunk(
  'auth/logoutUser',
  async (_, { rejectWithValue }) => {
    try {
      const refresh_token = localStorage.getItem('refresh_token');
      if (refresh_token) {
        await axios.post(`${API_BASE_URL}/api/accounts/auth/logout/`, {
          refresh_token
        });
      }
    } catch (err) {
      console.error('Logout error', err);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
    }
  }
);

// --------------------------
// Slice
// --------------------------
const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setUser: (state, action: PayloadAction<User>) => {
      state.user = action.payload;
      state.isAuthenticated = true;
    },
  },
  extraReducers: (builder) => {
    // Login
    builder.addCase(loginUser.pending, (state) => {
      state.isLoading = true;
      state.error = null;
    });
    builder.addCase(loginUser.fulfilled, (state, action) => {
      state.isLoading = false;
      state.isAuthenticated = true;
      state.user = action.payload.user;
      state.token = action.payload.access;
      state.error = null;
    });
    builder.addCase(loginUser.rejected, (state, action) => {
      state.isLoading = false;
      state.isAuthenticated = false;
      state.user = null;
      state.token = null;
      state.error = action.payload || 'Login failed';
    });

    // Register
    builder.addCase(registerUser.pending, (state) => {
      state.isLoading = true;
      state.error = null;
    });
    builder.addCase(registerUser.fulfilled, (state, action) => {
      state.isLoading = false;
      state.isAuthenticated = true;
      state.user = action.payload.user;
      state.token = action.payload.tokens.access;
      state.error = null;
    });
    builder.addCase(registerUser.rejected, (state, action) => {
      state.isLoading = false;
      state.isAuthenticated = false;
      state.user = null;
      state.token = null;
      state.error = action.payload || 'Registration failed';
    });

    // Logout
    builder.addCase(logoutUser.fulfilled, (state) => {
      state.user = null;
      state.token = null;
      state.isAuthenticated = false;
    });
  },
});

export const { clearError, setUser } = authSlice.actions;
export const authReducer = authSlice.reducer;
export default authSlice.reducer;
