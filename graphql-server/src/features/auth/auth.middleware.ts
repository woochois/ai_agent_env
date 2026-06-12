import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { AuthService } from './auth.service';

/**
 * Middleware that verifies JWT Bearer tokens on incoming requests.
 * - Extracts Bearer token from Authorization header
 * - Verifies token via AuthService.verifyAccessToken()
 * - Injects userId into req object for downstream use (PostGraphile pgSettings, custom mutations)
 * - Returns 401 Unauthorized for invalid/missing tokens
 */
@Injectable()
export class AuthMiddleware implements NestMiddleware {
  constructor(private readonly authService: AuthService) {}

  use(req: Request, res: Response, next: NextFunction): void {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      res.status(401).json({ message: 'Unauthorized: Missing or invalid Authorization header' });
      return;
    }

    const token = authHeader.slice(7); // Remove 'Bearer ' prefix

    try {
      const payload = this.authService.verifyAccessToken(token);
      // Attach userId to request for downstream access
      (req as any).userId = payload.userId;
      next();
    } catch {
      res.status(401).json({ message: 'Unauthorized: Invalid or expired token' });
      return;
    }
  }
}
