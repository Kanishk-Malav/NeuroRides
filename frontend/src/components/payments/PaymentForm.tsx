import React, { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { CreditCard, Lock, Loader2 } from 'lucide-react';
import { RootState } from '../../store';
import { processPayment } from '../../store/slices/paymentsSlice';
import { PaymentMethod } from '../../types';

interface PaymentFormProps {
  rideId: string;
  amount: number;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const PaymentForm: React.FC<PaymentFormProps> = ({
  rideId,
  amount,
  onSuccess,
  onCancel
}) => {
  const dispatch = useDispatch();
  const { loading, error } = useSelector((state: RootState) => state.payments);
  
  const [paymentMethod, setPaymentMethod] = useState<'card' | 'wallet'>('card');
  const [cardData, setCardData] = useState({
    cardNumber: '',
    expiryDate: '',
    cvv: '',
    cardholderName: ''
  });
  const [saveCard, setSaveCard] = useState(false);

  const formatCardNumber = (value: string) => {
    const v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
    const matches = v.match(/\d{4,16}/g);
    const match = matches && matches[0] || '';
    const parts = [];
    
    for (let i = 0, len = match.length; i < len; i += 4) {
      parts.push(match.substring(i, i + 4));
    }
    
    if (parts.length) {
      return parts.join(' ');
    } else {
      return v;
    }
  };

  const formatExpiryDate = (value: string) => {
    const v = value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
    if (v.length >= 2) {
      return v.substring(0, 2) + '/' + v.substring(2, 4);
    }
    return v;
  };

  const handleCardInputChange = (field: string, value: string) => {
    let formattedValue = value;
    
    if (field === 'cardNumber') {
      formattedValue = formatCardNumber(value);
    } else if (field === 'expiryDate') {
      formattedValue = formatExpiryDate(value);
    } else if (field === 'cvv') {
      formattedValue = value.replace(/[^0-9]/g, '').substring(0, 4);
    }
    
    setCardData({
      ...cardData,
      [field]: formattedValue
    });
  };

  const validateCard = () => {
    const errors: string[] = [];
    
    if (cardData.cardNumber.replace(/\s/g, '').length < 13) {
      errors.push('Invalid card number');
    }
    
    if (!cardData.expiryDate.match(/^\d{2}\/\d{2}$/)) {
      errors.push('Invalid expiry date');
    }
    
    if (cardData.cvv.length < 3) {
      errors.push('Invalid CVV');
    }
    
    if (!cardData.cardholderName.trim()) {
      errors.push('Cardholder name is required');
    }
    
    return errors;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (paymentMethod === 'card') {
      const validationErrors = validateCard();
      if (validationErrors.length > 0) {
        alert(validationErrors.join('\n'));
        return;
      }
    }

    const paymentData = {
      ride_id: rideId,
      amount,
      payment_method: paymentMethod,
      ...(paymentMethod === 'card' && {
        card_number: cardData.cardNumber.replace(/\s/g, ''),
        expiry_date: cardData.expiryDate,
        cvv: cardData.cvv,
        cardholder_name: cardData.cardholderName,
        save_card: saveCard
      })
    };

    try {
      await dispatch(processPayment(paymentData) as any).unwrap();
      onSuccess?.();
    } catch (error) {
      // Error handled by Redux slice
    }
  };

  const getCardType = (cardNumber: string) => {
    const number = cardNumber.replace(/\s/g, '');
    if (number.startsWith('4')) return 'visa';
    if (number.startsWith('5') || number.startsWith('2')) return 'mastercard';
    if (number.startsWith('3')) return 'amex';
    return 'unknown';
  };

  return (
    <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-6">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Complete Payment</h2>
        <div className="mt-2 text-3xl font-bold text-primary-600">
          ${amount.toFixed(2)}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Payment Method Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Payment Method
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setPaymentMethod('card')}
              className={`p-3 border rounded-lg text-center ${
                paymentMethod === 'card'
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <CreditCard className="h-6 w-6 mx-auto mb-1" />
              <div className="text-sm font-medium">Credit Card</div>
            </button>
            <button
              type="button"
              onClick={() => setPaymentMethod('wallet')}
              className={`p-3 border rounded-lg text-center ${
                paymentMethod === 'wallet'
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="h-6 w-6 mx-auto mb-1 bg-gradient-to-r from-purple-500 to-pink-500 rounded"></div>
              <div className="text-sm font-medium">Digital Wallet</div>
            </button>
          </div>
        </div>

        {/* Card Payment Form */}
        {paymentMethod === 'card' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Card Number
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={cardData.cardNumber}
                  onChange={(e) => handleCardInputChange('cardNumber', e.target.value)}
                  placeholder="1234 5678 9012 3456"
                  maxLength={19}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                  <CreditCard className="h-4 w-4 text-gray-400" />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expiry Date
                </label>
                <input
                  type="text"
                  value={cardData.expiryDate}
                  onChange={(e) => handleCardInputChange('expiryDate', e.target.value)}
                  placeholder="MM/YY"
                  maxLength={5}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  CVV
                </label>
                <input
                  type="text"
                  value={cardData.cvv}
                  onChange={(e) => handleCardInputChange('cvv', e.target.value)}
                  placeholder="123"
                  maxLength={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Cardholder Name
              </label>
              <input
                type="text"
                value={cardData.cardholderName}
                onChange={(e) => handleCardInputChange('cardholderName', e.target.value)}
                placeholder="John Doe"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="flex items-center">
              <input
                id="save-card"
                type="checkbox"
                checked={saveCard}
                onChange={(e) => setSaveCard(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="save-card" className="ml-2 block text-sm text-gray-700">
                Save this card for future payments
              </label>
            </div>
          </div>
        )}

        {/* Digital Wallet */}
        {paymentMethod === 'wallet' && (
          <div className="text-center py-8">
            <div className="text-gray-500 mb-4">
              Digital wallet integration will be available soon
            </div>
            <button
              type="button"
              onClick={() => setPaymentMethod('card')}
              className="text-primary-600 hover:text-primary-500"
            >
              Use credit card instead
            </button>
          </div>
        )}

        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <div className="text-sm text-red-700">{error}</div>
          </div>
        )}

        {/* Security Notice */}
        <div className="flex items-center justify-center text-sm text-gray-500">
          <Lock className="h-4 w-4 mr-1" />
          Your payment information is secure and encrypted
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-3">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 py-2 px-4 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={loading || (paymentMethod === 'wallet')}
            className="flex-1 bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : null}
            Pay ${amount.toFixed(2)}
          </button>
        </div>
      </form>
    </div>
  );
};

export default PaymentForm;