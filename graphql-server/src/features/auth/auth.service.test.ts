import * as jwt from 'jsonwebtoken';
import * as bcrypt from 'bcrypt';
import { AuthService } from './auth.service';

// Mock pg Pool
jest.mock('pg', () => {
  const mockQuery = jest.fn();
  const mockEnd = jest.fn();
  return {
    Pool: jest.fn(() => ({
      query: mockQuery,
      end: mockEnd,
    })),
  };
});

describe('AuthService', () => {
  let service: AuthService;
  let mockPool: { query: jest.Mock; end: jest.Mock };

  const JWT_SECRET = 'playground-jwt-secret-key';
  const JWT_REFRESH_SECRET = 'playground-refresh-secret-key';

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.JWT_SECRET = JWT_SECRET;
    process.env.JWT_REFRESH_SECRET = JWT_REFRESH_SECRET;

    service = new AuthService();

    // Get reference to the mocked pool
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { Pool } = require('pg');
    mockPool = Pool.mock.results[Pool.mock.results.length - 1].value;
  });

  describe('login', () => {
    it('should return tokens and userId for valid credentials', async () => {
      const hashedPassword = await bcrypt.hash('admin123', 10);
      mockPool.query.mockResolvedValueOnce({
        rows: [{ user_id: 1, user_password: hashedPassword }],
      });

      const result = await service.login('admin@playground.local', 'admin123');

      expect(result.userId).toBe(1);
      expect(result.accessToken).toBeDefined();
      expect(result.refreshToken).toBeDefined();

      // Verify the access token is valid
      const decoded = jwt.verify(result.accessToken, JWT_SECRET) as { userId: number };
      expect(decoded.userId).toBe(1);

      // Verify the refresh token is valid
      const refreshDecoded = jwt.verify(result.refreshToken, JWT_REFRESH_SECRET) as { userId: number };
      expect(refreshDecoded.userId).toBe(1);
    });

    it('should throw "Invalid credentials" if user not found', async () => {
      mockPool.query.mockResolvedValueOnce({ rows: [] });

      await expect(
        service.login('nonexistent@test.com', 'password'),
      ).rejects.toThrow('Invalid credentials');
    });

    it('should throw "Invalid credentials" if password is wrong', async () => {
      const hashedPassword = await bcrypt.hash('correctpassword', 10);
      mockPool.query.mockResolvedValueOnce({
        rows: [{ user_id: 1, user_password: hashedPassword }],
      });

      await expect(
        service.login('admin@playground.local', 'wrongpassword'),
      ).rejects.toThrow('Invalid credentials');
    });

    it('should query only non-deleted users', async () => {
      mockPool.query.mockResolvedValueOnce({ rows: [] });

      await service.login('test@test.com', 'pass').catch(() => {});

      expect(mockPool.query).toHaveBeenCalledWith(
        'SELECT user_id, user_password FROM users WHERE user_email = $1 AND is_deleted = false',
        ['test@test.com'],
      );
    });
  });

  describe('refresh', () => {
    it('should return new tokens for a valid refresh token', async () => {
      const refreshToken = jwt.sign({ userId: 42 }, JWT_REFRESH_SECRET, {
        expiresIn: 3600,
      });

      const result = await service.refresh(refreshToken);

      expect(result.userId).toBe(42);
      expect(result.accessToken).toBeDefined();
      expect(result.refreshToken).toBeDefined();

      // Verify new access token
      const decoded = jwt.verify(result.accessToken, JWT_SECRET) as { userId: number };
      expect(decoded.userId).toBe(42);
    });

    it('should throw "Invalid refresh token" for expired token', async () => {
      const expiredToken = jwt.sign({ userId: 1 }, JWT_REFRESH_SECRET, {
        expiresIn: -10, // already expired
      });

      await expect(service.refresh(expiredToken)).rejects.toThrow(
        'Invalid refresh token',
      );
    });

    it('should throw "Invalid refresh token" for token signed with wrong secret', async () => {
      const badToken = jwt.sign({ userId: 1 }, 'wrong-secret', {
        expiresIn: 3600,
      });

      await expect(service.refresh(badToken)).rejects.toThrow(
        'Invalid refresh token',
      );
    });
  });

  describe('verifyAccessToken', () => {
    it('should return decoded payload for valid token', () => {
      const token = jwt.sign({ userId: 7 }, JWT_SECRET, { expiresIn: 3600 });

      const result = service.verifyAccessToken(token);

      expect(result).toEqual({ userId: 7 });
    });

    it('should throw "Invalid access token" for expired token', () => {
      const expiredToken = jwt.sign({ userId: 1 }, JWT_SECRET, {
        expiresIn: -10,
      });

      expect(() => service.verifyAccessToken(expiredToken)).toThrow(
        'Invalid access token',
      );
    });

    it('should throw "Invalid access token" for token with wrong secret', () => {
      const badToken = jwt.sign({ userId: 1 }, 'wrong-secret', {
        expiresIn: 3600,
      });

      expect(() => service.verifyAccessToken(badToken)).toThrow(
        'Invalid access token',
      );
    });
  });

  describe('logout', () => {
    it('should return success true', async () => {
      const result = await service.logout();
      expect(result).toEqual({ success: true });
    });
  });
});
