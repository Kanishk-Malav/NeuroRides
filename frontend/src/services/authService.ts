import { apiService } from './api';
import { User, LoginCredentials, RegisterData } from '../types';

interface LoginResponse {
  user: User;
  token: string;
  refresh_token?: string;
}

interface RegisterResponse {
  user: User;
  message: string;
}

class AuthService {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    return apiService.post<LoginResponse>('/accounts/login/', credentials);
  }

  async register(userData: RegisterData): Promise<RegisterResponse> {
    return apiService.post<RegisterResponse>('/accounts/register/', userData);
  }

  async logout(): Promise<void> {
    return apiService.post<void>('/accounts/logout/');
  }

  async getCurrentUser(): Promise<User> {
    return apiService.get<User>('/accounts/profile/');
  }

  async updateProfile(userData: Partial<User>): Promise<User> {
    return apiService.patch<User>('/accounts/profile/', userData);
  }

  async changePassword(data: { old_password: string; new_password: string }): Promise<void> {
    return apiService.post<void>('/accounts/change-password/', data);
  }

  async requestPasswordReset(email: string): Promise<void> {
    return apiService.post<void>('/accounts/password-reset/', { email });
  }

  async confirmPasswordReset(data: { token: string; password: string }): Promise<void> {
    return apiService.post<void>('/accounts/password-reset-confirm/', data);
  }

  async verifyEmail(token: string): Promise<void> {
    return apiService.post<void>('/accounts/verify-email/', { token });
  }

  async resendVerificationEmail(): Promise<void> {
    return apiService.post<void>('/accounts/resend-verification/');
  }

  // Token management
  getToken(): string | null {
    return localStorage.getItem('token');
  }

  setToken(token: string): void {
    localStorage.setItem('token', token);
  }

  removeToken(): void {
    localStorage.removeItem('token');
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) return false;

    try {
      // Check if token is expired (basic JWT check)
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp > currentTime;
    } catch {
      return false;
    }
  }
}

export const authService = new AuthService();