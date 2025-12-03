import { ReactNode } from "react";

// User and Authentication Types
export type UserRole = 'rider' | 'operator' | 'admin';

export interface User {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  role: UserRole;
  is_verified: boolean;
  created_at: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  role: 'rider' | 'operator';
}

// Ride Types
export interface Ride {
  id: string;
  rider: string;
  vehicle?: string;
  assigned_vehicle?: Vehicle;
  pickup_latitude: number;
  pickup_longitude: number;
  pickup_address: string;
  destination_latitude: number;
  destination_longitude: number;
  destination_address: string;
  status: 'pending' | 'assigned' | 'en_route_to_pickup' | 'arrived_at_pickup' | 'in_progress' | 'completed' | 'cancelled' | 'payment_failed';
  fare_estimate: number;
  fare?: string;
  final_fare?: number;
  requested_at: string;
  created_at: string;
  assigned_at?: string;
  picked_up_at?: string;
  completed_at?: string;
  estimated_distance_km?: number;
  estimated_duration_minutes?: number;
  actual_distance_km?: number;
  actual_duration_minutes?: number;
}

export interface RideRequest {
  pickup_latitude: number;
  pickup_longitude: number;
  pickup_address: string;
  destination_latitude: number;
  destination_longitude: number;
  destination_address: string;
}

// Vehicle Types
export interface Vehicle {
  id: string;
  license_plate: string;
  make: string;
  model: string;
  vehicle_type: 'compact' | 'sedan' | 'suv' | 'luxury';
  status: 'idle' | 'assigned' | 'in_ride' | 'maintenance' | 'offline';
  current_location: {
    latitude: number;
    longitude: number;
  };
  current_latitude?: number;
  current_longitude?: number;
  battery_level?: number;
  mileage?: number;
  is_active: boolean;
  last_maintenance?: string;
}

// Payment Types
export interface PaymentMethod {
  id: string;
  payment_type: 'credit_card' | 'debit_card' | 'digital_wallet';
  card_brand?: string;
  last_four_digits?: string;
  expiry_month?: number;
  expiry_year?: number;
  cardholder_name?: string;
  is_default: boolean;
  is_active: boolean;
  display_name: string;
}

export interface Payment {
  id: string;
  ride?: Ride;
  amount: string;
  currency: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'refunded';
  payment_method: string;
  transaction_id?: string;
  created_at: string;
  processed_at?: string;
}

export interface FareEstimate {
  duration_minutes: ReactNode;
  estimated_fare: number;
  fare_range: {
    min: number;
    max: number;
  };
  fare_breakdown: {
    base_fare: number;
    distance_fare: number;
    time_fare: number;
    surge_multiplier: number;
    taxes_and_fees: number;
  };
  distance_km: number;
  estimated_duration_minutes: number;
  surge_active: boolean;
}

// Analytics Types
export interface RideAnalytics {
  id: string;
  date: string;
  hour?: number;
  total_rides: number;
  completed_rides: number;
  cancelled_rides: number;
  completion_rate: number;
  avg_distance_km: number;
  avg_duration_minutes: number;
  avg_wait_time_minutes: number;
}

export interface RevenueAnalytics {
  id: string;
  date: string;
  hour?: number;
  total_revenue: number;
  net_revenue: number;
  total_transactions: number;
  successful_transactions: number;
  transaction_success_rate: number;
  avg_transaction_value: number;
}

export interface FleetAnalytics {
  id: string;
  date: string;
  hour?: number;
  total_vehicles: number;
  active_vehicles: number;
  utilization_rate: number;
  avg_rides_per_vehicle: number;
  avg_response_time_minutes: number;
}

export interface DashboardData {
  total_rides_today: number;
  total_revenue_today: number;
  active_vehicles: number;
  active_users_today: number;
  rides_trend: number;
  revenue_trend: number;
  fleet_utilization_trend: number;
  user_growth_trend: number;
}

export interface KPI {
  name: string;
  value: number;
  unit: string;
  trend_percentage?: number;
  trend_direction?: 'up' | 'down' | 'stable';
  target_value?: number;
  status: 'good' | 'warning' | 'critical';
}

export interface ChartDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface ChartData {
  chart_type: 'line' | 'bar' | 'pie' | 'area';
  title: string;
  x_axis_label: string;
  y_axis_label: string;
  data_points: ChartDataPoint[];
}

// WebSocket Types
export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
}

export interface RideUpdate {
  ride_id: string;
  status: string;
  vehicle_location?: {
    latitude: number;
    longitude: number;
  };
  estimated_arrival?: string;
  message?: string;
}

export interface VehicleUpdate {
  vehicle_id: string;
  location: {
    latitude: number;
    longitude: number;
  };
  status: string;
  battery_level: number;
  speed?: number;
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Form Types
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'email' | 'password' | 'tel' | 'select' | 'textarea';
  placeholder?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  validation?: {
    pattern?: RegExp;
    minLength?: number;
    maxLength?: number;
    custom?: (value: string) => string | null;
  };
}

// Map Types
export interface MapLocation {
  latitude: number;
  longitude: number;
  address?: string;
}

export interface Location {
  latitude: number;
  longitude: number;
  address: string;
  name?: string;
}

export interface MapBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

// Notification Types
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  action?: {
    label: string;
    url: string;
  };
}

// Redux Store Types
export interface RootState {
  auth: AuthState;
  rides: RidesState;
  vehicles: VehiclesState;
  payments: PaymentsState;
  analytics: AnalyticsState;
  notifications: NotificationsState;
  ui: UIState;
}

export interface RidesState {
  currentRide: Ride | null;
  rideHistory: Ride[];
  rides: Ride[];
  fareEstimate: FareEstimate | null;
  isLoading: boolean;
  loading: boolean;
  error: string | null;
}

export interface VehiclesState {
  vehicles: Vehicle[];
  selectedVehicle: Vehicle | null;
  isLoading: boolean;
  loading: boolean;
  error: string | null;
}

export interface PaymentsState {
  paymentMethods: PaymentMethod[];
  payments: Payment[];
  isLoading: boolean;
  loading: boolean;
  error: string | null;
}

export interface AnalyticsState {
  dashboardData: DashboardData | null;
  kpis: KPI[];
  chartData: { [key: string]: ChartData };
  analytics: any;
  isLoading: boolean;
  loading: boolean;
  error: string | null;
}

export interface NotificationsState {
  notifications: Notification[];
  unreadCount: number;
}

export interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  loading: { [key: string]: boolean };
}