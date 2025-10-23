import { apiService } from './api';
import { PaymentMethod, Payment, PaginatedResponse } from '../types';

class PaymentsService {
  async getPaymentMethods(): Promise<PaymentMethod[]> {
    return apiService.get<PaymentMethod[]>('/payments/methods/');
  }

  async addPaymentMethod(paymentMethodData: Partial<PaymentMethod>): Promise<PaymentMethod> {
    return apiService.post<PaymentMethod>('/payments/methods/', paymentMethodData);
  }

  async updatePaymentMethod(paymentMethodId: string, data: Partial<PaymentMethod>): Promise<PaymentMethod> {
    return apiService.put<PaymentMethod>(`/payments/methods/${paymentMethodId}/`, data);
  }

  async deletePaymentMethod(paymentMethodId: string): Promise<void> {
    return apiService.delete<void>(`/payments/methods/${paymentMethodId}/`);
  }

  async setDefaultPaymentMethod(paymentMethodId: string): Promise<PaymentMethod> {
    return apiService.patch<PaymentMethod>(`/payments/methods/${paymentMethodId}/`, {
      is_default: true
    });
  }

  async processPayment(paymentData: { rideId: string; paymentMethodId: string }): Promise<Payment> {
    return apiService.post<Payment>('/payments/create/', {
      ride_id: paymentData.rideId,
      payment_method_id: paymentData.paymentMethodId
    });
  }

  async confirmPayment(paymentId: string, paymentMethodId: string): Promise<Payment> {
    return apiService.post<Payment>(`/payments/${paymentId}/confirm/`, {
      payment_method_id: paymentMethodId
    });
  }

  async getPaymentHistory(page = 1, pageSize = 20): Promise<Payment[]> {
    const response = await apiService.get<PaginatedResponse<Payment>>('/payments/', {
      params: { page, page_size: pageSize }
    });
    return response.results;
  }

  async getPaymentById(paymentId: string): Promise<Payment> {
    return apiService.get<Payment>(`/payments/${paymentId}/`);
  }

  async requestRefund(paymentId: string, reason: string, amount?: number): Promise<any> {
    return apiService.post<any>(`/payments/${paymentId}/refund/`, {
      reason,
      amount
    });
  }

  async getPaymentReceipt(paymentId: string, format = 'json'): Promise<any> {
    return apiService.get<any>(`/payments/${paymentId}/receipt/`, {
      params: { format }
    });
  }

  async validatePromoCode(code: string, rideAmount?: number): Promise<any> {
    return apiService.post<any>('/payments/promo-codes/validate/', {
      code,
      ride_amount: rideAmount
    });
  }

  async getPaymentStatistics(): Promise<any> {
    return apiService.get<any>('/payments/statistics/');
  }

  // Payment gateway specific methods
  async createStripePaymentIntent(amount: number, currency = 'USD'): Promise<any> {
    return apiService.post<any>('/payments/stripe/create-intent/', {
      amount,
      currency
    });
  }

  async confirmStripePayment(paymentIntentId: string, paymentMethodId: string): Promise<any> {
    return apiService.post<any>('/payments/stripe/confirm/', {
      payment_intent_id: paymentIntentId,
      payment_method_id: paymentMethodId
    });
  }
}

export const paymentsService = new PaymentsService();