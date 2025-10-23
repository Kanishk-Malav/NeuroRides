import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import { Icon } from 'leaflet';
import { Car, MapPin, Clock, Phone, MessageCircle } from 'lucide-react';
import { RootState } from '../../store';
import { websocketService } from '../../services/websocketService';
import { updateRideStatus } from '../../store/slices/ridesSlice';
import { Ride, Vehicle } from '../../types';
import 'leaflet/dist/leaflet.css';

interface RideTrackerProps {
  rideId: string;
}

// Custom icons for map markers
const riderIcon = new Icon({
  iconUrl: '/icons/rider-marker.png',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
  shadowUrl: '/icons/marker-shadow.png',
  shadowSize: [41, 41]
});

const vehicleIcon = new Icon({
  iconUrl: '/icons/vehicle-marker.png',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
  shadowUrl: '/icons/marker-shadow.png',
  shadowSize: [41, 41]
});

const destinationIcon = new Icon({
  iconUrl: '/icons/destination-marker.png',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  popupAnchor: [0, -32],
  shadowUrl: '/icons/marker-shadow.png',
  shadowSize: [41, 41]
});

const RideTracker: React.FC<RideTrackerProps> = ({ rideId }) => {
  const dispatch = useDispatch();
  const { currentRide } = useSelector((state: RootState) => state.rides);
  const [vehicleLocation, setVehicleLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [estimatedArrival, setEstimatedArrival] = useState<string | null>(null);
  const [route, setRoute] = useState<[number, number][]>([]);

  useEffect(() => {
    if (!rideId) return;

    // Connect to WebSocket for real-time updates
    websocketService.connect();
    
    // Join ride tracking room
    websocketService.joinRideTracking(rideId);

    // Listen for ride updates
    const handleRideUpdate = (data: any) => {
      if (data.ride_id === rideId) {
        dispatch(updateRideStatus(data));
        
        if (data.vehicle_location) {
          setVehicleLocation({
            lat: data.vehicle_location.latitude,
            lng: data.vehicle_location.longitude
          });
        }
        
        if (data.estimated_arrival) {
          setEstimatedArrival(data.estimated_arrival);
        }
        
        if (data.route) {
          setRoute(data.route.map((point: any) => [point.latitude, point.longitude]));
        }
      }
    };

    websocketService.onRideUpdate(handleRideUpdate);

    return () => {
      websocketService.leaveRideTracking(rideId);
      websocketService.disconnect();
    };
  }, [rideId, dispatch]);

  if (!currentRide) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        <span className="ml-2">Loading ride details...</span>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'text-yellow-600 bg-yellow-100';
      case 'assigned': return 'text-blue-600 bg-blue-100';
      case 'en_route_to_pickup': return 'text-purple-600 bg-purple-100';
      case 'arrived_at_pickup': return 'text-green-600 bg-green-100';
      case 'in_progress': return 'text-indigo-600 bg-indigo-100';
      case 'completed': return 'text-green-600 bg-green-100';
      case 'cancelled': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending': return 'Finding a driver...';
      case 'assigned': return 'Driver assigned';
      case 'en_route_to_pickup': return 'Driver is on the way';
      case 'arrived_at_pickup': return 'Driver has arrived';
      case 'in_progress': return 'Trip in progress';
      case 'completed': return 'Trip completed';
      case 'cancelled': return 'Trip cancelled';
      default: return status;
    }
  };

  const mapCenter: [number, number] = vehicleLocation 
    ? [vehicleLocation.lat, vehicleLocation.lng]
    : [currentRide.pickup_latitude, currentRide.pickup_longitude];

  return (
    <div className="bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Status Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Your Ride</h2>
            <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(currentRide.status)}`}>
              {getStatusText(currentRide.status)}
            </div>
          </div>
          {estimatedArrival && (
            <div className="text-right">
              <div className="text-sm text-gray-500">Estimated arrival</div>
              <div className="font-semibold text-primary-600">
                <Clock className="inline h-4 w-4 mr-1" />
                {estimatedArrival}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="h-64 relative">
        <MapContainer
          center={mapCenter}
          zoom={14}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
          
          {/* Pickup Location */}
          <Marker
            position={[currentRide.pickup_latitude, currentRide.pickup_longitude]}
            icon={riderIcon}
          >
            <Popup>
              <div>
                <strong>Pickup Location</strong>
                <br />
                {currentRide.pickup_address}
              </div>
            </Popup>
          </Marker>

          {/* Destination */}
          <Marker
            position={[currentRide.destination_latitude, currentRide.destination_longitude]}
            icon={destinationIcon}
          >
            <Popup>
              <div>
                <strong>Destination</strong>
                <br />
                {currentRide.destination_address}
              </div>
            </Popup>
          </Marker>

          {/* Vehicle Location */}
          {vehicleLocation && (
            <Marker position={[vehicleLocation.lat, vehicleLocation.lng]} icon={vehicleIcon}>
              <Popup>
                <div>
                  <strong>Your Driver</strong>
                  <br />
                  {currentRide.assigned_vehicle?.license_plate}
                </div>
              </Popup>
            </Marker>
          )}

          {/* Route */}
          {route.length > 0 && (
            <Polyline
              positions={route}
              color="#3B82F6"
              weight={4}
              opacity={0.7}
            />
          )}
        </MapContainer>
      </div>

      {/* Driver Info */}
      {currentRide.assigned_vehicle && (
        <div className="p-4 border-t bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="h-12 w-12 bg-primary-100 rounded-full flex items-center justify-center">
                <Car className="h-6 w-6 text-primary-600" />
              </div>
              <div className="ml-3">
                <div className="font-medium text-gray-900">
                  {currentRide.assigned_vehicle.license_plate}
                </div>
                <div className="text-sm text-gray-500">
                  {currentRide.assigned_vehicle.make} {currentRide.assigned_vehicle.model}
                </div>
              </div>
            </div>
            
            <div className="flex space-x-2">
              <button className="p-2 bg-white rounded-full shadow-sm border hover:bg-gray-50">
                <Phone className="h-4 w-4 text-gray-600" />
              </button>
              <button className="p-2 bg-white rounded-full shadow-sm border hover:bg-gray-50">
                <MessageCircle className="h-4 w-4 text-gray-600" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trip Details */}
      <div className="p-4 border-t">
        <div className="space-y-3">
          <div className="flex items-start">
            <MapPin className="h-4 w-4 text-green-500 mt-1 mr-2" />
            <div>
              <div className="text-sm font-medium text-gray-900">Pickup</div>
              <div className="text-sm text-gray-500">{currentRide.pickup_address}</div>
            </div>
          </div>
          
          <div className="flex items-start">
            <MapPin className="h-4 w-4 text-red-500 mt-1 mr-2" />
            <div>
              <div className="text-sm font-medium text-gray-900">Destination</div>
              <div className="text-sm text-gray-500">{currentRide.destination_address}</div>
            </div>
          </div>
          
          {currentRide.fare && (
            <div className="flex items-center justify-between pt-2 border-t">
              <span className="text-sm font-medium text-gray-900">Fare</span>
              <span className="text-lg font-bold text-primary-600">
                ${currentRide.fare}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RideTracker;