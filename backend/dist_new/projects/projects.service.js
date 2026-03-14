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
exports.ProjectsService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma.service");
const contracts_service_1 = require("../contracts/contracts.service");
let ProjectsService = class ProjectsService {
    constructor(prisma, contractsService) {
        this.prisma = prisma;
        this.contractsService = contractsService;
    }
    async findAllForUser(userId) {
        const projects = await this.prisma.projects.findMany({
            where: {
                deleted_at: null,
                OR: [
                    { owner_user_id: userId },
                    {
                        project_collaborators: {
                            some: { user_id: userId },
                        },
                    },
                ],
            },
            include: {
                venues: {
                    select: {
                        id: true,
                        name: true,
                    },
                },
                project_pricing: {
                    select: {
                        id: true,
                        project_id: true,
                    },
                    take: 1,
                },
                events: {
                    select: {
                        id: true,
                        event_type: true,
                    },
                    take: 1,
                },
            },
            orderBy: { created_at: 'desc' },
        });
        return projects.map((project) => ({
            id: project.id,
            name: project.title,
            event_type: project.events?.[0]?.event_type || 'general',
            event_date: project.event_date,
            event_end_date: project.event_end_date,
            guest_count: project.guest_count,
            status: project.status,
            total_price: null,
            venue_name: project.venues?.name,
            venue_id: project.venue_id,
            created_at: project.created_at,
            updated_at: project.updated_at,
        }));
    }
    async findById(id) {
        const project = await this.prisma.projects.findFirst({
            where: { id, deleted_at: null },
            include: {
                contracts_contracts_project_idToprojects: {
                    where: { is_active: true },
                    orderBy: { version_number: 'desc' },
                    take: 1,
                },
            },
        });
        if (!project) {
            throw new common_1.NotFoundException(`Project with id ${id} not found`);
        }
        const latestActiveContract = project.contracts_contracts_project_idToprojects.length > 0
            ? project.contracts_contracts_project_idToprojects[0]
            : null;
        const { contracts_contracts_project_idToprojects, ...projectData } = project;
        return {
            ...projectData,
            latestActiveContract,
        };
    }
    async create(userId, dto) {
        return this.prisma.$transaction(async (tx) => {
            const project = await tx.projects.create({
                data: {
                    owner_user_id: userId,
                    title: dto.title,
                    event_date: dto.eventDate ? new Date(dto.eventDate) : null,
                    event_end_date: dto.eventEndDate ? new Date(dto.eventEndDate) : null,
                    guest_count: dto.guestCount ?? null,
                },
            });
            await tx.project_collaborators.create({
                data: {
                    project_id: project.id,
                    user_id: userId,
                },
            });
            return project;
        });
    }
    async createFromAiIntake(dto, userId) {
        let validatedMenuItems = dto.menu_items || [];
        if (validatedMenuItems.length > 0) {
            const dbItems = await this.prisma.menu_items.findMany({
                where: { active: true },
                select: { name: true },
            });
            const dbNameSet = new Set(dbItems.map((i) => i.name.toLowerCase()));
            const filtered = validatedMenuItems.filter((item) => {
                const nameLower = item.toLowerCase().replace(/\s*\(.*?\)/g, '').trim();
                return (dbNameSet.has(nameLower) ||
                    [...dbNameSet].some((db) => db.includes(nameLower) || nameLower.includes(db)));
            });
            if (filtered.length !== validatedMenuItems.length) {
                console.warn(`[AI Intake] Filtered out non-DB menu items. Before: ${validatedMenuItems.join(', ')} | After: ${filtered.join(', ')}`);
            }
            validatedMenuItems = filtered;
        }
        const result = await this.prisma.$transaction(async (tx) => {
            const project = await tx.projects.create({
                data: {
                    owner_user_id: userId,
                    title: dto.event_type && dto.client_name
                        ? `${dto.event_type} - ${dto.client_name}`
                        : dto.client_name || dto.event_type || 'AI Generated Event',
                    event_date: dto.event_date ? new Date(dto.event_date) : null,
                    guest_count: dto.guest_count ?? null,
                    status: 'draft',
                    created_via_ai_intake: true,
                    ai_event_summary: JSON.stringify(dto),
                },
            });
            let venue = null;
            if (dto.venue_name) {
                venue = await tx.venues.findFirst({
                    where: { name: dto.venue_name },
                });
                if (!venue) {
                    venue = await tx.venues.create({
                        data: {
                            name: dto.venue_name,
                            address: dto.venue_address || '',
                        },
                    });
                }
                await tx.projects.update({
                    where: { id: project.id },
                    data: { venue_id: venue.id },
                });
            }
            await tx.project_collaborators.create({
                data: {
                    project_id: project.id,
                    user_id: userId,
                },
            });
            let contract = null;
            if (dto.generate_contract) {
                console.log(`📝 [Contract] Generating contract for project ${project.id}`);
                console.log(`👤 [Contract] Client: ${dto.client_name} (${dto.contact_email})`);
                console.log(`📅 [Contract] Event: ${dto.event_type} on ${dto.event_date}`);
                console.log(`👥 [Contract] Guest count: ${dto.guest_count}`);
                contract = await tx.contracts.create({
                    data: {
                        project_id: project.id,
                        contract_group_id: project.id,
                        version_number: 1,
                        status: 'pending_staff_approval',
                        title: `Contract - ${dto.event_type || 'Event'} for ${dto.client_name || 'Client'}`,
                        body: {
                            client_info: {
                                name: dto.client_name,
                                email: dto.contact_email,
                                phone: dto.contact_phone,
                            },
                            event_details: {
                                type: dto.event_type,
                                date: dto.event_date,
                                guest_count: dto.guest_count,
                                service_type: dto.service_type,
                                venue: {
                                    name: dto.venue_name,
                                    address: dto.venue_address,
                                },
                            },
                            menu: {
                                items: validatedMenuItems,
                                dietary_restrictions: dto.dietary_restrictions || [],
                                notes: dto.menu_notes || undefined,
                            },
                            logistics: {
                                setup_time: dto.setup_time,
                                service_time: dto.service_time,
                            },
                            additional: {
                                addons: dto.addons || [],
                                modifications: dto.modifications || [],
                                budget_range: dto.budget_range,
                            },
                        },
                        is_active: true,
                        created_by: userId,
                    },
                });
                console.log(`✅ [Contract] Contract created with ID: ${contract.id}`);
                console.log(`📋 [Contract] Status: pending_staff_approval - Awaiting staff review`);
            }
            return {
                project,
                venue,
                contract,
                contract_data: dto,
            };
        });
        if (result.contract) {
            console.log(`📄 [Contract] Enqueuing PDF generation for contract ${result.contract.id}`);
            await this.contractsService.enqueuePdfGeneration(result.contract.id, userId);
            console.log(`✅ [Contract] Contract ${result.contract.id} created and queued for PDF generation`);
            console.log(`⏳ [Contract] Status: ${result.contract.status} - Awaiting staff approval`);
            console.log(`📧 [Contract] Client email: ${dto.contact_email}`);
        }
        console.log(`✅ [Project] Project ${result.project.id} created successfully`);
        console.log(`📊 [Project] Event type: ${dto.event_type}, Guest count: ${dto.guest_count}`);
        return result;
    }
};
exports.ProjectsService = ProjectsService;
exports.ProjectsService = ProjectsService = __decorate([
    (0, common_1.Injectable)(),
    __param(1, (0, common_1.Inject)((0, common_1.forwardRef)(() => contracts_service_1.ContractsService))),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService,
        contracts_service_1.ContractsService])
], ProjectsService);
//# sourceMappingURL=projects.service.js.map