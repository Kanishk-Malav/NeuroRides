import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Car, Users, AlertTriangle, TrendingUp, Battery } from 'lucide-react';
import { RootState } from '../../store';
// import { getVehicles } from '../../store/slices/vehiclesSlice';
import { fetchAnalytics, fetchVehicles } from '../../store/slices/analyticsSlice';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { Icon } from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Custom vehicle status icons
const vehicleIcons = {
  idle: new Icon({
    iconUrl: '/icons/vehicle-idle.png',
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    popupAnchor: [0, -24]
  }),
  assigned: new Icon({
    iconUrl: '/icons/vehicle-assigned.png',
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    popupAnchor: [0, -24]
  }),
  in_ride: new Icon({
    iconUrl: '/icons/vehicle-in-ride.png',
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    popupAnchor: [0, -24]
  }),
  maintenance: new Icon({
    iconUrl: '/icons/vehicle-maintenance.png',
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    popupAnchor: [0, -24]
  })
};

const OperatorDashboard: React.FC = () => {
  const dispatch = useDispatch();
  // const newLocal = useSelector((state: RootState) => state.auth);
  const { vehicles } = useSelector((state: RootState) => state.vehicles);
  const { analytics } = useSelector((state: RootState) => state.analytics);
  const [selectedTimeRange, setSelectedTimeRange] = useState<'today' | 'week' | 'month'>('today');

  useEffect(() => {
    dispatch(fetchVehicles() as any);
    dispatch(fetchAnalytics() as any);
  }, [dispatch, selectedTimeRange]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'idle': return 'text-green-600 bg-green-100';
      case 'assigned': return 'text-blue-600 bg-blue-100';
      case 'in_ride': return 'text-purple-600 bg-purple-100';
      case 'maintenance': return 'text-red-600 bg-red-100';
      case 'offline': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getBatteryColor = (level: number) => {
    if (level > 50) return 'text-green-600';
    if (level > 20) return 'text-yellow-600';
    return 'text-red-600';
  };

  const vehicleStats = {
    total: vehicles.length,
    idle: vehicles.filter(v => v.status === 'idle').length,
    assigned: vehicles.filter(v => v.status === 'assigned').length,
    in_ride: vehicles.filter(v => v.status === 'in_ride').length,
    maintenance: vehicles.filter(v => v.status === 'maintenance').length,
    offline: vehicles.filter(v => v.status === 'offline').length
  };

  const maintenanceAlerts = vehicles.filter(v => 
    v.status === 'maintenance' || 
    (v.battery_level && v.battery_level < 20) ||
    (v.mileage && v.mileage > 50000)
  );

  // Default map center (San Francisco)
  const mapCenter: [number, number] = [37.7749, -122.4194];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  Fleet Operations
                </h1>
                <p className="mt-1 text-gray-500">
                  Monitor and manage your vehicle fleet
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <select
                  value={selectedTimeRange}
                  onChange={(e) => setSelectedTimeRange(e.target.value as any)}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="today">Today</option>
                  <option value="week">This Week</option>
                  <option value="month">This Month</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Car className="h-8 w-8 text-primary-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Total Vehicles</p>
                <p className="text-2xl font-semibold text-gray-900">{vehicleStats.total}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Users className="h-8 w-8 text-green-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Active Rides</p>
                <p className="text-2xl font-semibold text-gray-900">{vehicleStats.in_ride}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <TrendingUp className="h-8 w-8 text-blue-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Revenue Today</p>
                <p className="text-2xl font-semibold text-gray-900">
                  ${analytics?.revenue?.today || '0.00'}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <AlertTriangle className="h-8 w-8 text-red-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Maintenance Alerts</p>
                <p className="text-2xl font-semibold text-gray-900">{maintenanceAlerts.length}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Fleet Map */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow">
              <div className="p-6 border-b">
                <h2 className="text-xl font-semibold text-gray-900">Fleet Location</h2>
              </div>
              <div className="h-96">
                <MapContainer
                  center={mapCenter}
                  zoom={12}
                  style={{ height: '100%', width: '100%' }}
                >
                  <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  />
                  
                  {vehicles.map((vehicle) => (
                    vehicle.current_latitude && vehicle.current_longitude && (
                      <Marker
                        key={vehicle.id}
                        position={[vehicle.current_latitude, vehicle.current_longitude]}
                        icon={vehicleIcons[vehicle.status as keyof typeof vehicleIcons] || vehicleIcons.idle}
                      >
                        <Popup>
                          <div className="p-2">
                            <div className="font-semibold">{vehicle.license_plate}</div>
                            <div className="text-sm text-gray-600">
                              {vehicle.make} {vehicle.model}
                            </div>
                            <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium mt-1 ${getStatusColor(vehicle.status)}`}>
                              {vehicle.status.replace('_', ' ')}
                            </div>
                            {vehicle.battery_level && (
                              <div className="flex items-center mt-1 text-sm">
                                <Battery className={`h-3 w-3 mr-1 ${getBatteryColor(vehicle.battery_level)}`} />
                                {vehicle.battery_level}%
                              </div>
                            )}
                          </div>
                        </Popup>
                      </Marker>
                    )
                  ))}
                </MapContainer>
              </div>
            </div>
          </div>

          {/* Vehicle Status & Alerts */}
          <div className="space-y-6">
            {/* Vehicle Status Breakdown */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900">Vehicle Status</h3>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="w-3 h-3 bg-green-500 rounded-full mr-3"></div>
                    <span className="text-sm text-gray-600">Idle</span>
                  </div>
                  <span className="font-semibold">{vehicleStats.idle}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="w-3 h-3 bg-blue-500 rounded-full mr-3"></div>
                    <span className="text-sm text-gray-600">Assigned</span>
                  </div>
                  <span className="font-semibold">{vehicleStats.assigned}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="w-3 h-3 bg-purple-500 rounded-full mr-3"></div>
                    <span className="text-sm text-gray-600">In Ride</span>
                  </div>
                  <span className="font-semibold">{vehicleStats.in_ride}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="w-3 h-3 bg-red-500 rounded-full mr-3"></div>
                    <span className="text-sm text-gray-600">Maintenance</span>
                  </div>
                  <span className="font-semibold">{vehicleStats.maintenance}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="w-3 h-3 bg-gray-500 rounded-full mr-3"></div>
                    <span className="text-sm text-gray-600">Offline</span>
                  </div>
                  <span className="font-semibold">{vehicleStats.offline}</span>
                </div>
              </div>
            </div>

            {/* Maintenance Alerts */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900">Maintenance Alerts</h3>
              </div>
              <div className="divide-y divide-gray-200">
                {maintenanceAlerts.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    No maintenance alerts
                  </div>
                ) : (
                  maintenanceAlerts.slice(0, 5).map((vehicle) => (
                    <div key={vehicle.id} className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-gray-900">
                            {vehicle.license_plate}
                          </div>
                          <div className="text-sm text-gray-500">
                            {vehicle.make} {vehicle.model}
                          </div>
                        </div>
                        <div className="text-right">
                          {vehicle.status === 'maintenance' && (
                            <div className="text-xs text-red-600 font-medium">
                              Maintenance Required
                            </div>
                          )}
                          {vehicle.battery_level && vehicle.battery_level < 20 && (
                            <div className="text-xs text-red-600 font-medium">
                              Low Battery: {vehicle.battery_level}%
                            </div>
                          )}
                          {vehicle.mileage && vehicle.mileage > 50000 && (
                            <div className="text-xs text-yellow-600 font-medium">
                              High Mileage: {vehicle.mileage.toLocaleString()} mi
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-6 border-b">
                <h3 className="text-lg font-semibold text-gray-900">Performance</h3>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Fleet Utilization</span>
                  <span className="font-semibold">
                    {vehicleStats.total > 0 
                      ? Math.round(((vehicleStats.assigned + vehicleStats.in_ride) / vehicleStats.total) * 100)
                      : 0}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Avg Response Time</span>
                  <span className="font-semibold">
                    {analytics?.performance?.avg_response_time || '0'} min
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Completed Rides</span>
                  <span className="font-semibold">
                    {analytics?.rides?.completed || 0}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OperatorDashboard;