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
var StaffGuard_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.StaffGuard = void 0;
const common_1 = require("@nestjs/common");
const core_1 = require("@nestjs/core");
let StaffGuard = StaffGuard_1 = class StaffGuard {
    constructor(reflector) {
        this.reflector = reflector;
        this.logger = new common_1.Logger(StaffGuard_1.name);
        this.allowedDomains = ['@flashbacklabs.com', '@flashbacklabs.inc'];
    }
    canActivate(context) {
        const request = context.switchToHttp().getRequest();
        const user = request.user;
        if (!user || !user.email) {
            this.logger.warn(`🚫 [Staff Guard] Access denied - No user or email found`);
            throw new common_1.ForbiddenException('Authentication required');
        }
        const isStaff = this.allowedDomains.some(domain => user.email.toLowerCase().endsWith(domain.toLowerCase()));
        if (!isStaff) {
            this.logger.warn(`🚫 [Staff Guard] Access denied - ${user.email} is not a staff member`);
            this.logger.warn(`🚫 [Staff Guard] Allowed domains: ${this.allowedDomains.join(', ')}`);
            throw new common_1.ForbiddenException('Staff access required. Only @flashbacklabs.com or @flashbacklabs.inc accounts can access this resource.');
        }
        this.logger.log(`✅ [Staff Guard] Access granted - ${user.email} is staff`);
        return true;
    }
};
exports.StaffGuard = StaffGuard;
exports.StaffGuard = StaffGuard = StaffGuard_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [core_1.Reflector])
], StaffGuard);
//# sourceMappingURL=staff.guard.js.map