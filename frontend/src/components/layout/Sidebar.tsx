import React from 'react';
import { useSelector } from 'react-redux';
import { Link, useLocation } from 'react-router-dom';
import { 
  Home, Car, Users, BarChart3, CreditCard, 
  MapPin, Settings, History, Plus, AlertTriangle 
} from 'lucide-react';
import { RootState } from '../../store';

const Sidebar: React.FC = () => {
  const location = useLocation();
  const { user } = useSelector((state: RootState) => state.auth);
  const { sidebarOpen } = useSelector((state: RootState) => state.ui);

  const getNavigationItems = () => {
    const baseItems = [
      { name: 'Dashboard', href: '/dashboard', icon: Home }
    ];

    switch (user?.role) {
      case 'rider':
        return [
          ...baseItems,
          { name: 'Book Ride', href: '/book-ride', icon: Plus },
          { name: 'Ride History', href: '/ride-history', icon: History },
          { name: 'Payment Methods', href: '/payment-methods', icon: CreditCard },
          { name: 'Saved Places', href: '/saved-places', icon: MapPin }
        ];
      
      case 'operator':
        return [
          ...baseItems,
          { name: 'Fleet Management', href: '/fleet', icon: Car },
          { name: 'Active Rides', href: '/active-rides', icon: MapPin },
          { name: 'Maintenance', href: '/maintenance', icon: AlertTriangle },
          { name: 'Analytics', href: '/analytics', icon: BarChart3 }
        ];
      
      case 'admin':
        return [
          ...baseItems,
          { name: 'Analytics', href: '/admin/analytics', icon: BarChart3 },
          { name: 'User Management', href: '/admin/users', icon: Users },
          { name: 'Fleet Overview', href: '/admin/fleet', icon: Car },
          { name: 'Financial Reports', href: '/admin/finance', icon: CreditCard },
          { name: 'System Settings', href: '/admin/settings', icon: Settings }
        ];
      
      default:
        return baseItems;
    }
  };

  const navigationItems = getNavigationItems();

  const isActive = (href: string) => {
    return location.pathname === href || 
           (href !== '/dashboard' && location.pathname.startsWith(href));
  };

  return (
    <div className={`fixed inset-y-0 left-0 z-40 ${sidebarOpen ? 'w-64' : 'w-16'} bg-white shadow-lg border-r border-gray-200 transition-all duration-300 mt-16`}>
      <div className="flex flex-col h-full">
        <nav className="flex-1 px-2 py-4 space-y-1">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive(item.href)
                    ? 'bg-primary-100 text-primary-900 border-r-2 border-primary-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon
                  className={`${sidebarOpen ? 'mr-3' : 'mx-auto'} flex-shrink-0 h-5 w-5 transition-colors ${
                    isActive(item.href) ? 'text-primary-600' : 'text-gray-400 group-hover:text-gray-500'
                  }`}
                />
                {sidebarOpen && (
                  <span className="truncate">{item.name}</span>
                )}
                {!sidebarOpen && (
                  <span className="sr-only">{item.name}</span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* User Role Badge */}
        {sidebarOpen && (
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="h-8 w-8 bg-primary-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-medium text-primary-600 uppercase">
                    {user?.role?.charAt(0)}
                  </span>
                </div>
              </div>
              <div className="ml-3">
                <p className="text-sm font-medium text-gray-900 capitalize">
                  {user?.role} Account
                </p>
                <p className="text-xs text-gray-500">
                  {user?.email}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;