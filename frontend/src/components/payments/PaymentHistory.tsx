import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Download, Receipt, Calendar, DollarSign } from 'lucide-react';
import { RootState } from '../../store';
import { getPaymentHistory } from '../../store/slices/paymentsSlice';
// import { Payment } from '../../types';

const PaymentHistory: React.FC = () => {
  const dispatch = useDispatch();
  const { payments, loading } = useSelector((state: RootState) => state.payments);
  const [filter, setFilter] = useState<'all' | 'completed' | 'failed' | 'refunded'>('all');
  const [dateRange, setDateRange] = useState({
    startDate: '',
    endDate: ''
  });

  useEffect(() => {
    dispatch(getPaymentHistory() as any);
  }, [dispatch]);

  const filteredPayments = payments.filter(payment => {
    if (filter !== 'all' && payment.status !== filter) {
      return false;
    }
    
    if (dateRange.startDate && new Date(payment.created_at) < new Date(dateRange.startDate)) {
      return false;
    }
    
    if (dateRange.endDate && new Date(payment.created_at) > new Date(dateRange.endDate)) {
      return false;
    }
    
    return true;
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'failed': return 'text-red-600 bg-red-100';
      case 'refunded': return 'text-yellow-600 bg-yellow-100';
      case 'pending': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const downloadReceipt = (paymentId: string) => {
    // In a real app, this would download the receipt PDF
    console.log('Downloading receipt for payment:', paymentId);
  };

  const exportPayments = () => {
    // Convert payments to CSV and download
    const csvContent = [
      ['Date', 'Amount', 'Status', 'Payment Method', 'Transaction ID'].join(','),
      ...filteredPayments.map(payment => [
        formatDate(payment.created_at),
        payment.amount,
        payment.status,
        payment.payment_method,
        payment.transaction_id || ''
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'payment-history.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        <span className="ml-2">Loading payment history...</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="p-6 border-b">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Payment History</h2>
          <button
            onClick={exportPayments}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="p-6 border-b bg-gray-50">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status Filter
            </label>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as any)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="all">All Payments</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="refunded">Refunded</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <input
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange({ ...dateRange, startDate: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              End Date
            </label>
            <input
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange({ ...dateRange, endDate: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
      </div>

      {/* Payment List */}
      <div className="divide-y divide-gray-200">
        {filteredPayments.length === 0 ? (
          <div className="p-12 text-center">
            <DollarSign className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No payments found</h3>
            <p className="text-gray-500">
              {filter === 'all' 
                ? "You haven't made any payments yet."
                : `No ${filter} payments found for the selected criteria.`
              }
            </p>
          </div>
        ) : (
          filteredPayments.map((payment) => (
            <div key={payment.id} className="p-6 hover:bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center">
                      <div className="text-lg font-semibold text-gray-900">
                        ${payment.amount}
                      </div>
                      <div className={`ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(payment.status)}`}>
                        {payment.status}
                      </div>
                    </div>
                    <div className="text-sm text-gray-500">
                      <Calendar className="inline h-4 w-4 mr-1" />
                      {formatDate(payment.created_at)}
                    </div>
                  </div>
                  
                  <div className="text-sm text-gray-600 mb-2">
                    <strong>Payment Method:</strong> {payment.payment_method}
                    {payment.transaction_id && (
                      <>
                        <br />
                        <strong>Transaction ID:</strong> {payment.transaction_id}
                      </>
                    )}
                  </div>
                  
                  {payment.ride && (
                    <div className="text-sm text-gray-500">
                      <strong>Ride:</strong> {payment.ride.pickup_address} → {payment.ride.destination_address}
                    </div>
                  )}
                </div>
                
                <div className="ml-4 flex items-center space-x-2">
                  {payment.status === 'completed' && (
                    <button
                      onClick={() => downloadReceipt(payment.id)}
                      className="p-2 text-gray-400 hover:text-gray-600"
                      title="Download Receipt"
                    >
                      <Receipt className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Summary */}
      {filteredPayments.length > 0 && (
        <div className="p-6 border-t bg-gray-50">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-gray-900">
                {filteredPayments.length}
              </div>
              <div className="text-sm text-gray-500">Total Payments</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">
                ${filteredPayments
                  .filter(p => p.status === 'completed')
                  .reduce((sum, p) => sum + parseFloat(p.amount), 0)
                  .toFixed(2)}
              </div>
              <div className="text-sm text-gray-500">Total Paid</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red-600">
                ${filteredPayments
                  .filter(p => p.status === 'refunded')
                  .reduce((sum, p) => sum + parseFloat(p.amount), 0)
                  .toFixed(2)}
              </div>
              <div className="text-sm text-gray-500">Total Refunded</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaymentHistory;