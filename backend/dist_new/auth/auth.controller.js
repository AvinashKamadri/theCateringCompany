"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthController = void 0;
const common_1 = require("@nestjs/common");
const passport_1 = require("@nestjs/passport");
const auth_service_1 = require("./auth.service");
const public_decorator_1 = require("../common/decorators/public.decorator");
let AuthController = class AuthController {
    constructor(authService) {
        this.authService = authService;
    }
    async signup(body, res) {
        const { user, accessToken, refreshToken } = await this.authService.signup(body.email, body.password, {
            primary_phone: body.primary_phone,
            first_name: body.first_name,
            last_name: body.last_name,
        });
        this.setAccessTokenCookie(res, accessToken);
        this.setRefreshTokenCookie(res, refreshToken);
        return {
            user: {
                id: user.id,
                email: user.email,
                primary_phone: user.primary_phone,
                status: user.status,
                created_at: user.created_at,
                updated_at: user.updated_at,
            },
        };
    }
    async login(body, res) {
        const { user, accessToken, refreshToken } = await this.authService.login(body.email, body.password);
        this.setAccessTokenCookie(res, accessToken);
        this.setRefreshTokenCookie(res, refreshToken);
        return {
            user: {
                id: user.id,
                email: user.email,
                primary_phone: user.primary_phone,
                status: user.status,
                created_at: user.created_at,
                updated_at: user.updated_at,
            },
        };
    }
    async logout(req, res) {
        const user = req.user;
        await this.authService.logout(user.sessionId);
        res.clearCookie('app_jwt', { path: '/' });
        res.clearCookie('refresh_token', { path: '/' });
        return { message: 'Logged out successfully' };
    }
    async refresh(req, res) {
        const refreshTokenValue = req.cookies?.['refresh_token'];
        if (!refreshTokenValue) {
            throw new common_1.UnauthorizedException('No refresh token provided');
        }
        const { accessToken, refreshToken } = await this.authService.refresh(refreshTokenValue);
        this.setAccessTokenCookie(res, accessToken);
        this.setRefreshTokenCookie(res, refreshToken);
        return { message: 'Tokens refreshed successfully' };
    }
    async me(req) {
        const user = req.user;
        const dbUser = await this.authService.validateUser(user.userId);
        if (!dbUser) {
            throw new common_1.UnauthorizedException('User not found');
        }
        return {
            user: {
                id: dbUser.id,
                email: dbUser.email,
                primary_phone: dbUser.primary_phone,
                status: dbUser.status,
                created_at: dbUser.created_at,
                updated_at: dbUser.updated_at,
            },
        };
    }
    setAccessTokenCookie(res, token) {
        res.cookie('app_jwt', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 2 * 60 * 60 * 1000,
        });
    }
    setRefreshTokenCookie(res, token) {
        res.cookie('refresh_token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 7 * 24 * 60 * 60 * 1000,
        });
    }
};
exports.AuthController = AuthController;
__decorate([
    (0, public_decorator_1.Public)(),
    (0, common_1.Post)('signup'),
    __param(0, (0, common_1.Body)()),
    __param(1, (0, common_1.Res)({ passthrough: true })),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], AuthController.prototype, "signup", null);
__decorate([
    (0, public_decorator_1.Public)(),
    (0, common_1.Post)('login'),
    (0, common_1.HttpCode)(common_1.HttpStatus.OK),
    __param(0, (0, common_1.Body)()),
    __param(1, (0, common_1.Res)({ passthrough: true })),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], AuthController.prototype, "login", null);
__decorate([
    (0, common_1.UseGuards)((0, passport_1.AuthGuard)('jwt')),
    (0, common_1.Post)('logout'),
    (0, common_1.HttpCode)(common_1.HttpStatus.OK),
    __param(0, (0, common_1.Req)()),
    __param(1, (0, common_1.Res)({ passthrough: true })),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], AuthController.prototype, "logout", null);
__decorate([
    (0, public_decorator_1.Public)(),
    (0, common_1.Post)('refresh'),
    (0, common_1.HttpCode)(common_1.HttpStatus.OK),
    __param(0, (0, common_1.Req)()),
    __param(1, (0, common_1.Res)({ passthrough: true })),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], AuthController.prototype, "refresh", null);
__decorate([
    (0, common_1.UseGuards)((0, passport_1.AuthGuard)('jwt')),
    (0, common_1.Get)('me'),
    __param(0, (0, common_1.Req)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], AuthController.prototype, "me", null);
exports.AuthController = AuthController = __decorate([
    (0, common_1.Controller)('auth'),
    __metadata("design:paramtypes", [auth_service_1.AuthService])
], AuthController);
//# sourceMappingURL=auth.controller.js.map