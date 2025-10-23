import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { MapPin, Clock, Car, CreditCard, Plus, History } from 'lucide-react';
import { RootState } from '../../store';
import { fetchUserRides } from '../../store/slices/ridesSlice';
import RideBookingForm from '../rides/RideBookingForm';
import RideTracker from '../rides/RideTracker';

const RiderDashboard: React.FC = () => {
  const dispatch = useDispatch();
  const { user } = useSelector((state: RootState) => state.auth);
  const { rides, currentRide, loading } = useSelector((state: RootState) => state.rides);

  useEffect(() => {
    dispatch(fetchUserRides() as any);
  }, [dispatch]);

  const recentRides = rides.slice(0, 3);
  const activeRide = currentRide || rides.find(ride => 
    ['pending', 'assigned', 'en_route_to_pickup', 'arrived_at_pickup', 'in_progress'].includes(ride.status)
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'cancelled': return 'text-red-600 bg-red-100';
      case 'in_progress': return 'text-blue-600 bg-blue-100';
      default: return 'text-yellow-600 bg-yellow-100';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <h1 className="text-3xl font-bold text-gray-900">
              Welcome back, {user?.first_name}!
            </h1>
            <p className="mt-1 text-gray-500">
              Ready for your next ride?
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-8">
            {/* Active Ride */}
            {activeRide ? (
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Current Ride</h2>
                <RideTracker rideId={activeRide.id} />
              </div>
            ) : (
              /* Quick Actions */
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Link
                    to="/book-ride"
                    className="bg-primary-600 text-white p-6 rounded-lg hover:bg-primary-700 transition-colors"
                  >
                    <div className="flex items-center">
                      <Plus className="h-8 w-8 mr-3" />
                      <div>
                        <div className="text-lg font-semibold">Book a Ride</div>
                        <div className="text-primary-100">Get started with a new trip</div>
                      </div>
                    </div>
                  </Link>
                  
                  <Link
                    to="/ride-history"
                    className="bg-white border-2 border-gray-200 p-6 rounded-lg hover:border-gray-300 transition-colors"
                  >
                    <div className="flex items-center">
                      <History className="h-8 w-8 mr-3 text-gray-600" />
                      <div>
                        <div className="text-lg font-semibold text-gray-900">Ride History</div>
                        <div className="text-gray-500">View past trips</div>
                      </div>
                    </div>
                  </Link>
                </div>
              </div>
            )}

            {/* Recent Rides */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">Recent Rides</h2>
                <Link
                  to="/ride-history"
                  className="text-primary-600 hover:text-primary-500 text-sm font-medium"
                >
                  View all
                </Link>
              </div>
              
              {loading ? (
                <div className="bg-white rounded-lg shadow p-6">
                  <div className="animate-pulse space-y-4">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="flex space-x-4">
                        <div className="rounded-full bg-gray-200 h-10 w-10"></div>
                        <div className="flex-1 space-y-2">
                          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                          <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : recentRides.length > 0 ? (
                <div className="bg-white rounded-lg shadow divide-y divide-gray-200">
                  {recentRides.map((ride) => (
                    <div key={ride.id} className="p-6 hover:bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                          <div className="flex-shrink-0">
                            <div className="h-10 w-10 bg-primary-100 rounded-full flex items-center justify-center">
                              <Car className="h-5 w-5 text-primary-600" />
                            </div>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2 mb-1">
                              <p className="text-sm font-medium text-gray-900 truncate">
                                {ride.pickup_address}
                              </p>
                              <span className="text-gray-400">→</span>
                              <p className="text-sm text-gray-500 truncate">
                                {ride.destination_address}
                              </p>
                            </div>
                            <div className="flex items-center space-x-4 text-xs text-gray-500">
                              <span className="flex items-center">
                                <Clock className="h-3 w-3 mr-1" />
                                {formatDate(ride.created_at)}
                              </span>
                              {ride.fare && (
                                <span className="flex items-center">
                                  <CreditCard className="h-3 w-3 mr-1" />
                                  ${ride.fare}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(ride.status)}`}>
                          {ride.status.replace('_', ' ')}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-white rounded-lg shadow p-12 text-center">
                  <Car className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No rides yet</h3>
                  <p className="text-gray-500 mb-6">
                    Book your first ride to get started with NeuroRides
                  </p>
                  <Link
                    to="/book-ride"
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Book Your First Ride
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Quick Book */}
            {!activeRide && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Book</h3>
                <RideBookingForm />
              </div>
            )}

            {/* Stats */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Your Stats</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Total Rides</span>
                  <span className="font-semibold">{rides.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">This Month</span>
                  <span className="font-semibold">
                    {rides.filter(ride => {
                      const rideDate = new Date(ride.created_at);
                      const now = new Date();
                      return rideDate.getMonth() === now.getMonth() && 
                             rideDate.getFullYear() === now.getFullYear();
                    }).length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Total Spent</span>
                  <span className="font-semibold">
                    ${rides
                      .filter(ride => ride.fare)
                      .reduce((sum, ride) => sum + parseFloat(ride.fare!), 0)
                      .toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Links */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Quick Links</h3>
              <div className="space-y-3">
                <Link
                  to="/payment-methods"
                  className="flex items-center text-gray-600 hover:text-primary-600"
                >
                  <CreditCard className="h-4 w-4 mr-3" />
                  Payment Methods
                </Link>
                <Link
                  to="/profile"
                  className="flex items-center text-gray-600 hover:text-primary-600"
                >
                  <MapPin className="h-4 w-4 mr-3" />
                  Saved Addresses
                </Link>
                <Link
                  to="/support"
                  className="flex items-center text-gray-600 hover:text-primary-600"
                >
                  <Clock className="h-4 w-4 mr-3" />
                  Support
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RiderDashboard;