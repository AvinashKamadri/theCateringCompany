"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContractsModule = void 0;
const common_1 = require("@nestjs/common");
const bullmq_1 = require("@nestjs/bullmq");
const contracts_controller_1 = require("./contracts.controller");
const staff_contracts_controller_1 = require("./staff-contracts.controller");
const contracts_service_1 = require("./contracts.service");
const contract_pdf_service_1 = require("./contract-pdf.service");
const prisma_service_1 = require("../prisma.service");
const opensign_module_1 = require("../opensign/opensign.module");
const staff_guard_1 = require("../common/guards/staff.guard");
const pricing_service_1 = require("../pricing/pricing.service");
let ContractsModule = class ContractsModule {
};
exports.ContractsModule = ContractsModule;
exports.ContractsModule = ContractsModule = __decorate([
    (0, common_1.Module)({
        imports: [
            bullmq_1.BullModule.registerQueue({
                name: 'pdf_generation',
            }),
            opensign_module_1.OpenSignModule,
        ],
        controllers: [contracts_controller_1.ContractsController, staff_contracts_controller_1.StaffContractsController],
        providers: [contracts_service_1.ContractsService, contract_pdf_service_1.ContractPdfService, prisma_service_1.PrismaService, staff_guard_1.StaffGuard, pricing_service_1.PricingService],
        exports: [contracts_service_1.ContractsService],
    })
], ContractsModule);
//# sourceMappingURL=contracts.module.js.map