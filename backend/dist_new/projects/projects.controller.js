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
exports.ProjectsController = void 0;
const common_1 = require("@nestjs/common");
const passport_1 = require("@nestjs/passport");
const projects_service_1 = require("./projects.service");
const current_user_decorator_1 = require("../common/decorators/current-user.decorator");
let ProjectsController = class ProjectsController {
    constructor(projectsService) {
        this.projectsService = projectsService;
    }
    async findAll(user) {
        return this.projectsService.findAllForUser(user.userId);
    }
    async findOne(id, user) {
        return this.projectsService.findById(id);
    }
    async create(user, body) {
        return this.projectsService.create(user.userId, body);
    }
    async createFromAiIntake(user, body) {
        try {
            console.log('🎯 [API] Creating project from AI intake for user:', user.userId);
            console.log('📦 [API] Request body:', JSON.stringify(body, null, 2));
            const result = await this.projectsService.createFromAiIntake(body, user.userId);
            console.log('✅ [API] Project created successfully:', result.project.id);
            console.log('📋 [API] Contract created:', result.contract?.id || 'No contract');
            console.log('📤 [API] Returning result:', JSON.stringify({
                project: { id: result.project.id, title: result.project.title },
                contract: result.contract ? { id: result.contract.id, status: result.contract.status } : null,
                venue: result.venue ? { id: result.venue.id, name: result.venue.name } : null,
            }, null, 2));
            return result;
        }
        catch (error) {
            console.error('❌ [API] Error creating project from AI intake:', error);
            console.error('❌ [API] Error stack:', error.stack);
            console.error('❌ [API] Error message:', error.message);
            throw error;
        }
    }
};
exports.ProjectsController = ProjectsController;
__decorate([
    (0, common_1.Get)(),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], ProjectsController.prototype, "findAll", null);
__decorate([
    (0, common_1.Get)(':id'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], ProjectsController.prototype, "findOne", null);
__decorate([
    (0, common_1.Post)(),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], ProjectsController.prototype, "create", null);
__decorate([
    (0, common_1.Post)('ai-intake'),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, Object]),
    __metadata("design:returntype", Promise)
], ProjectsController.prototype, "createFromAiIntake", null);
exports.ProjectsController = ProjectsController = __decorate([
    (0, common_1.UseGuards)((0, passport_1.AuthGuard)('jwt')),
    (0, common_1.Controller)('projects'),
    __metadata("design:paramtypes", [projects_service_1.ProjectsService])
], ProjectsController);
//# sourceMappingURL=projects.controller.js.map