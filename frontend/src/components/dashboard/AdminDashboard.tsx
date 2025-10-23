import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Area, AreaChart
} from 'recharts';
import { 
  TrendingUp, Users, Car, DollarSign, AlertTriangle, 
  Calendar, Download, Filter, RefreshCw 
} from 'lucide-react';
import { RootState } from '../../store';
import { fetchAnalytics } from '../../store/slices/analyticsSlice';
import { fetchVehicles } from '../../store/slices/vehiclesSlice';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

const AdminDashboard: React.FC = () => {
  const dispatch = useDispatch();
  const { analytics, loading: analyticsLoading } = useSelector((state: RootState) => state.analytics);
  const { vehicles } = useSelector((state: RootState) => state.vehicles);
  const [timeRange, setTimeRange] = useState<'today' | 'week' | 'month' | 'year'>('month');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    dispatch(fetchAnalytics({ timeRange }) as any);
    dispatch(fetchVehicles() as any);
  }, [dispatch, timeRange]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      dispatch(fetchAnalytics({ timeRange }) as any),
      dispatch(fetchVehicles() as any)
    ]);
    setRefreshing(false);
  };

  const exportData = () => {
    // In a real app, this would generate and download a comprehensive report
    console.log('Exporting analytics data...');
  };

  // Mock data for charts (in production, this would come from analytics)
  const revenueData = [
    { name: 'Jan', revenue: 12000, rides: 450 },
    { name: 'Feb', revenue: 15000, rides: 520 },
    { name: 'Mar', revenue: 18000, rides: 680 },
    { name: 'Apr', revenue: 22000, rides: 750 },
    { name: 'May', revenue: 25000, rides: 820 },
    { name: 'Jun', revenue: 28000, rides: 900 }
  ];

  const rideStatusData = [
    { name: 'Completed', value: 85, color: '#10B981' },
    { name: 'Cancelled', value: 10, color: '#EF4444' },
    { name: 'In Progress', value: 5, color: '#3B82F6' }
  ];

  const fleetUtilizationData = [
    { name: 'Mon', utilization: 78 },
    { name: 'Tue', utilization: 82 },
    { name: 'Wed', utilization: 75 },
    { name: 'Thu', utilization: 88 },
    { name: 'Fri', utilization: 92 },
    { name: 'Sat', utilization: 95 },
    { name: 'Sun', utilization: 85 }
  ];

  const topMetrics = [
    {
      title: 'Total Revenue',
      value: `$${analytics?.revenue?.total || '0'}`,
      change: '+12.5%',
      changeType: 'positive' as const,
      icon: DollarSign,
      color: 'text-green-600'
    },
    {
      title: 'Active Users',
      value: analytics?.users?.active || '0',
      change: '+8.2%',
      changeType: 'positive' as const,
      icon: Users,
      color: 'text-blue-600'
    },
    {
      title: 'Fleet Size',
      value: vehicles.length.toString(),
      change: '+2.1%',
      changeType: 'positive' as const,
      icon: Car,
      color: 'text-purple-600'
    },
    {
      title: 'Avg Response Time',
      value: `${analytics?.performance?.avg_response_time || '0'} min`,
      change: '-5.3%',
      changeType: 'positive' as const,
      icon: TrendingUp,
      color: 'text-indigo-600'
    }
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  Analytics Dashboard
                </h1>
                <p className="mt-1 text-gray-500">
                  Comprehensive insights into your NeuroRides platform
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <select
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value as any)}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="today">Today</option>
                  <option value="week">This Week</option>
                  <option value="month">This Month</option>
                  <option value="year">This Year</option>
                </select>
                <button
                  onClick={handleRefresh}
                  disabled={refreshing}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                <button
                  onClick={exportData}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {topMetrics.map((metric, index) => (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <metric.icon className={`h-8 w-8 ${metric.color}`} />
                </div>
                <div className="ml-4 flex-1">
                  <p className="text-sm font-medium text-gray-500">{metric.title}</p>
                  <div className="flex items-baseline">
                    <p className="text-2xl font-semibold text-gray-900">{metric.value}</p>
                    <p className={`ml-2 text-sm font-medium ${
                      metric.changeType === 'positive' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {metric.change}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Revenue Trend */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-gray-900">Revenue & Rides Trend</h3>
              <div className="flex items-center space-x-2 text-sm text-gray-500">
                <div className="flex items-center">
                  <div className="w-3 h-3 bg-primary-600 rounded-full mr-2"></div>
                  Revenue
                </div>
                <div className="flex items-center">
                  <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                  Rides
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="revenue"
                  stackId="1"
                  stroke="#3B82F6"
                  fill="#3B82F6"
                  fillOpacity={0.6}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="rides"
                  stroke="#10B981"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Ride Status Distribution */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-6">Ride Status Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={rideStatusData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {rideStatusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Fleet Utilization */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">Fleet Utilization Rate</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={fleetUtilizationData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="utilization" fill="#3B82F6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Detailed Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Top Performing Routes */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold text-gray-900">Top Performing Routes</h3>
            </div>
            <div className="divide-y divide-gray-200">
              {[
                { route: 'Downtown → Airport', rides: 245, revenue: '$3,675' },
                { route: 'University → Mall', rides: 189, revenue: '$2,835' },
                { route: 'Hospital → Station', rides: 156, revenue: '$2,340' },
                { route: 'Beach → Downtown', rides: 134, revenue: '$2,010' },
                { route: 'Airport → Hotel District', rides: 98, revenue: '$1,470' }
              ].map((route, index) => (
                <div key={index} className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-gray-900">{route.route}</div>
                      <div className="text-sm text-gray-500">{route.rides} rides</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-gray-900">{route.revenue}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* System Alerts */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold text-gray-900">System Alerts</h3>
            </div>
            <div className="divide-y divide-gray-200">
              {[
                { 
                  type: 'warning', 
                  message: '3 vehicles require maintenance', 
                  time: '2 hours ago',
                  severity: 'medium'
                },
                { 
                  type: 'info', 
                  message: 'Peak hour surge pricing activated', 
                  time: '4 hours ago',
                  severity: 'low'
                },
                { 
                  type: 'error', 
                  message: 'Payment gateway timeout detected', 
                  time: '6 hours ago',
                  severity: 'high'
                },
                { 
                  type: 'success', 
                  message: 'Daily backup completed successfully', 
                  time: '8 hours ago',
                  severity: 'low'
                }
              ].map((alert, index) => (
                <div key={index} className="p-4">
                  <div className="flex items-start">
                    <div className="flex-shrink-0">
                      <AlertTriangle className={`h-5 w-5 ${
                        alert.severity === 'high' ? 'text-red-500' :
                        alert.severity === 'medium' ? 'text-yellow-500' :
                        'text-blue-500'
                      }`} />
                    </div>
                    <div className="ml-3 flex-1">
                      <p className="text-sm font-medium text-gray-900">{alert.message}</p>
                      <p className="text-xs text-gray-500 mt-1">{alert.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;