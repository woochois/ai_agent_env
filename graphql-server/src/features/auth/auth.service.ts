import { Injectable, OnModuleDestroy } from '@nestjs/common';
import { Pool } from 'pg';
import * as bcrypt from 'bcrypt';
import * as jwt from 'jsonwebtoken';

interface JwtPayload {
  userId: number;
}

@Injectable()
export class AuthService implements OnModuleDestroy {
  private readonly pool: Pool;
  private readonly jwtSecret: string;
  private readonly jwtRefreshSecret: string;
  private readonly accessTokenExpiry: number = 3600; // 1 hour in seconds
  private readonly refreshTokenExpiry: number = 604800; // 7 days in seconds

  constructor() {
    const connectionString =
      process.env.DATABASE_URL ||
      'postgres://user:password@postgres:5432/agent_db';

    this.pool = new Pool({ connectionString });
    this.jwtSecret = process.env.JWT_SECRET || 'playground-jwt-secret-key';
    this.jwtRefreshSecret =
      process.env.JWT_REFRESH_SECRET || 'playground-refresh-secret-key';
  }

  async onModuleDestroy(): Promise<void> {
    await this.pool.end();
  }

  async login(
    email: string,
    password: string,
  ): Promise<{ accessToken: string; refreshToken: string; userId: number }> {
    const result = await this.pool.query(
      'SELECT user_id, user_password FROM users WHERE user_email = $1 AND is_deleted = false',
      [email],
    );

    if (result.rows.length === 0) {
      throw new Error('Invalid credentials');
    }

    const user = result.rows[0];
    const isPasswordValid = await bcrypt.compare(password, user.user_password);

    if (!isPasswordValid) {
      throw new Error('Invalid credentials');
    }

    const userId: number = user.user_id;
    const accessToken = this.generateAccessToken(userId);
    const refreshToken = this.generateRefreshToken(userId);

    return { accessToken, refreshToken, userId };
  }

  async refresh(
    refreshToken: string,
  ): Promise<{ accessToken: string; refreshToken: string; userId: number }> {
    let payload: JwtPayload;

    try {
      payload = jwt.verify(refreshToken, this.jwtRefreshSecret) as JwtPayload;
    } catch {
      throw new Error('Invalid refresh token');
    }

    const userId = payload.userId;
    const newAccessToken = this.generateAccessToken(userId);
    const newRefreshToken = this.generateRefreshToken(userId);

    return {
      accessToken: newAccessToken,
      refreshToken: newRefreshToken,
      userId,
    };
  }

  verifyAccessToken(token: string): JwtPayload {
    try {
      const payload = jwt.verify(token, this.jwtSecret) as JwtPayload;
      return { userId: payload.userId };
    } catch {
      throw new Error('Invalid access token');
    }
  }

  async logout(): Promise<{ success: boolean }> {
    // Stateless JWT — client is responsible for discarding the token
    return { success: true };
  }

  private generateAccessToken(userId: number): string {
    return jwt.sign({ userId }, this.jwtSecret, {
      expiresIn: this.accessTokenExpiry,
    });
  }

  private generateRefreshToken(userId: number): string {
    return jwt.sign({ userId }, this.jwtRefreshSecret, {
      expiresIn: this.refreshTokenExpiry,
    });
  }
}
