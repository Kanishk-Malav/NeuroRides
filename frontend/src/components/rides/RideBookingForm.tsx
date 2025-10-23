import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { MapPin, Clock, DollarSign, Loader2 } from 'lucide-react';
import { RootState } from '../../store';
import { createRide, estimateFare } from '../../store/slices/ridesSlice';
import { LocationPicker } from './LocationPicker';
import { Location } from '../../types';

const RideBookingForm: React.FC = () => {
  const dispatch = useDispatch();
  const { loading, fareEstimate } = useSelector((state: RootState) => state.rides);
  
  const [pickupLocation, setPickupLocation] = useState<Location | null>(null);
  const [destinationLocation, setDestinationLocation] = useState<Location | null>(null);
  const [rideType, setRideType] = useState<'standard' | 'premium'>('standard');
  const [scheduledTime, setScheduledTime] = useState('');
  const [notes, setNotes] = useState('');
  const [showConfirmation, setShowConfirmation] = useState(false);

  // Estimate fare when locations change
  useEffect(() => {
    if (pickupLocation && destinationLocation) {
      dispatch(estimateFare({
        pickup_latitude: pickupLocation.latitude,
        pickup_longitude: pickupLocation.longitude,
        destination_latitude: destinationLocation.latitude,
        destination_longitude: destinationLocation.longitude,
        ride_type: rideType
      }) as any);
    }
  }, [pickupLocation, destinationLocation, rideType, dispatch]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!pickupLocation || !destinationLocation) {
      return;
    }

    const rideData = {
      pickup_latitude: pickupLocation.latitude,
      pickup_longitude: pickupLocation.longitude,
      pickup_address: pickupLocation.address,
      destination_latitude: destinationLocation.latitude,
      destination_longitude: destinationLocation.longitude,
      destination_address: destinationLocation.address,
      ride_type: rideType,
      scheduled_time: scheduledTime || undefined,
      notes: notes || undefined
    };

    try {
      await dispatch(createRide(rideData) as any).unwrap();
      setShowConfirmation(true);
    } catch (error) {
      // Error handled by Redux slice
    }
  };

  const resetForm = () => {
    setPickupLocation(null);
    setDestinationLocation(null);
    setRideType('standard');
    setScheduledTime('');
    setNotes('');
    setShowConfirmation(false);
  };

  if (showConfirmation) {
    return (
      <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
            <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 className="mt-4 text-lg font-medium text-gray-900">Ride Booked Successfully!</h3>
          <p className="mt-2 text-sm text-gray-500">
            Your ride has been requested. You'll receive updates about your driver assignment.
          </p>
          <div className="mt-6">
            <button
              onClick={resetForm}
              className="w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              Book Another Ride
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Book a Ride</h2>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Pickup Location */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <MapPin className="inline h-4 w-4 mr-1" />
            Pickup Location
          </label>
          <LocationPicker
            value={pickupLocation}
            onChange={setPickupLocation}
            placeholder="Enter pickup location"
          />
        </div>

        {/* Destination Location */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <MapPin className="inline h-4 w-4 mr-1" />
            Destination
          </label>
          <LocationPicker
            value={destinationLocation}
            onChange={setDestinationLocation}
            placeholder="Enter destination"
          />
        </div>

        {/* Ride Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Ride Type
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setRideType('standard')}
              className={`p-3 border rounded-lg text-center ${
                rideType === 'standard'
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="font-medium">Standard</div>
              <div className="text-sm text-gray-500">Affordable rides</div>
            </button>
            <button
              type="button"
              onClick={() => setRideType('premium')}
              className={`p-3 border rounded-lg text-center ${
                rideType === 'premium'
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="font-medium">Premium</div>
              <div className="text-sm text-gray-500">Luxury vehicles</div>
            </button>
          </div>
        </div>

        {/* Scheduled Time */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <Clock className="inline h-4 w-4 mr-1" />
            Schedule for Later (Optional)
          </label>
          <input
            type="datetime-local"
            value={scheduledTime}
            onChange={(e) => setScheduledTime(e.target.value)}
            min={new Date().toISOString().slice(0, 16)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Special Instructions (Optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            placeholder="Any special instructions for your driver..."
          />
        </div>

        {/* Fare Estimate */}
        {fareEstimate && (
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                <DollarSign className="inline h-4 w-4 mr-1" />
                Estimated Fare
              </span>
              <span className="text-lg font-bold text-primary-600">
                ${fareEstimate.estimated_fare}
              </span>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Distance: {fareEstimate.distance_km} km • 
              Duration: {fareEstimate.duration_minutes} min
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || !pickupLocation || !destinationLocation}
          className="w-full bg-primary-600 text-white py-3 px-4 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : null}
          {scheduledTime ? 'Schedule Ride' : 'Book Now'}
        </button>
      </form>
    </div>
  );
};

export default RideBookingForm;