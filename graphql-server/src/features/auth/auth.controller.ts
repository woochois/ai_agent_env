import {
  Controller,
  Post,
  Body,
  HttpCode,
  HttpStatus,
  HttpException,
} from '@nestjs/common';
import { AuthService } from './auth.service';

interface LoginDto {
  email: string;
  password: string;
}

interface RefreshDto {
  refreshToken: string;
}

interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  userId: number;
}

interface LogoutResponse {
  success: boolean;
}

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  async login(@Body() body: LoginDto): Promise<AuthResponse> {
    if (!body.email || !body.password) {
      throw new HttpException(
        'Email and password are required',
        HttpStatus.BAD_REQUEST,
      );
    }

    try {
      const result = await this.authService.login(body.email, body.password);
      return result;
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Authentication failed';
      if (message === 'Invalid credentials') {
        throw new HttpException(message, HttpStatus.UNAUTHORIZED);
      }
      throw new HttpException(message, HttpStatus.INTERNAL_SERVER_ERROR);
    }
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  async refresh(@Body() body: RefreshDto): Promise<AuthResponse> {
    if (!body.refreshToken) {
      throw new HttpException(
        'Refresh token is required',
        HttpStatus.BAD_REQUEST,
      );
    }

    try {
      const result = await this.authService.refresh(body.refreshToken);
      return result;
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Token refresh failed';
      if (
        message === 'Invalid refresh token' ||
        message === 'Refresh token expired'
      ) {
        throw new HttpException(message, HttpStatus.UNAUTHORIZED);
      }
      throw new HttpException(message, HttpStatus.INTERNAL_SERVER_ERROR);
    }
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
  async logout(): Promise<LogoutResponse> {
    const result = await this.authService.logout();
    return result;
  }
}
