import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from './store';
import { checkAuthStatus } from './store/slices/authSlice';

// Layout Components
import Layout from './components/layout/Layout';
import ProtectedRoute from './components/auth/ProtectedRoute';

// Auth Components
import LoginForm from './components/auth/LoginForm';
import RegisterForm from './components/auth/RegisterForm';
import ForgotPasswordForm from './components/auth/ForgotPasswordForm';

// Dashboard Components
import RiderDashboard from './components/dashboard/RiderDashboard';
import OperatorDashboard from './components/dashboard/OperatorDashboard';
import AdminDashboard from './components/dashboard/AdminDashboard';

// Ride Components
import RideBookingForm from './components/rides/RideBookingForm';
import RideTracker from './components/rides/RideTracker';

// Payment Components
import PaymentForm from './components/payments/PaymentForm';
import PaymentHistory from './components/payments/PaymentHistory';

function App() {
  const dispatch = useDispatch();
  const { isAuthenticated, loading, user } = useSelector((state: RootState) => state.auth);

  useEffect(() => {
    dispatch(checkAuthStatus() as any);
  }, [dispatch]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-secondary-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading NeuroRides...</p>
        </div>
      </div>
    );
  }

  const getDashboardComponent = () => {
    switch (user?.role) {
      case 'admin':
        return <AdminDashboard />;
      case 'operator':
        return <OperatorDashboard />;
      case 'rider':
      default:
        return <RiderDashboard />;
    }
  };

  return (
    <Router>
      <div className="min-h-screen bg-gray-50 pt-16">
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={
            <ProtectedRoute requireAuth={false}>
              <LoginForm />
            </ProtectedRoute>
          } />
          <Route path="/register" element={
            <ProtectedRoute requireAuth={false}>
              <RegisterForm />
            </ProtectedRoute>
          } />
          <Route path="/forgot-password" element={
            <ProtectedRoute requireAuth={false}>
              <ForgotPasswordForm />
            </ProtectedRoute>
          } />

          {/* Protected Routes */}
          <Route path="/" element={<Layout />}>
            <Route index element={
              <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />
            } />
            
            <Route path="dashboard" element={
              <ProtectedRoute>
                {getDashboardComponent()}
              </ProtectedRoute>
            } />

            {/* Rider Routes */}
            <Route path="book-ride" element={
              <ProtectedRoute requiredRole="rider">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <RideBookingForm />
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="ride-history" element={
              <ProtectedRoute requiredRole="rider">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <PaymentHistory />
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="ride/:rideId/track" element={
              <ProtectedRoute requiredRole="rider">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <RideTracker rideId={window.location.pathname.split('/')[2]} />
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="payment-methods" element={
              <ProtectedRoute requiredRole="rider">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <PaymentHistory />
                </div>
              </ProtectedRoute>
            } />

            {/* Operator Routes */}
            <Route path="fleet" element={
              <ProtectedRoute requiredRole="operator">
                <OperatorDashboard />
              </ProtectedRoute>
            } />
            
            <Route path="active-rides" element={
              <ProtectedRoute requiredRole="operator">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">Active Rides</h1>
                  <p className="text-gray-500">Active rides management interface will be implemented here.</p>
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="maintenance" element={
              <ProtectedRoute requiredRole="operator">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">Maintenance</h1>
                  <p className="text-gray-500">Vehicle maintenance interface will be implemented here.</p>
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="analytics" element={
              <ProtectedRoute requiredRole="operator">
                <AdminDashboard />
              </ProtectedRoute>
            } />

            {/* Admin Routes */}
            <Route path="admin/analytics" element={
              <ProtectedRoute requiredRole="admin">
                <AdminDashboard />
              </ProtectedRoute>
            } />
            
            <Route path="admin/users" element={
              <ProtectedRoute requiredRole="admin">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">User Management</h1>
                  <p className="text-gray-500">User management interface will be implemented here.</p>
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="admin/fleet" element={
              <ProtectedRoute requiredRole="admin">
                <OperatorDashboard />
              </ProtectedRoute>
            } />
            
            <Route path="admin/finance" element={
              <ProtectedRoute requiredRole="admin">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">Financial Reports</h1>
                  <PaymentHistory />
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="admin/settings" element={
              <ProtectedRoute requiredRole="admin">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">System Settings</h1>
                  <p className="text-gray-500">System settings interface will be implemented here.</p>
                </div>
              </ProtectedRoute>
            } />

            {/* Common Routes */}
            <Route path="profile" element={
              <ProtectedRoute>
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">Profile</h1>
                  <p className="text-gray-500">User profile interface will be implemented here.</p>
                </div>
              </ProtectedRoute>
            } />
            
            <Route path="settings" element={
              <ProtectedRoute>
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                  <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>
                  <p className="text-gray-500">User settings interface will be implemented here.</p>
                </div>
              </ProtectedRoute>
            } />

            {/* Catch all route */}
            <Route path="*" element={
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center py-12">
                <h1 className="text-4xl font-bold text-gray-900 mb-4">404 - Page Not Found</h1>
                <p className="text-gray-500 mb-8">The page you're looking for doesn't exist.</p>
                <Navigate to="/dashboard" replace />
              </div>
            } />
          </Route>
        </Routes>
      </div>
    </Router>
  );
}

export default App;