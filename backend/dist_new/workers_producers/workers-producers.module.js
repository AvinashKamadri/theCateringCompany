"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WorkersProducersModule = exports.QUEUE_NAMES = void 0;
const common_1 = require("@nestjs/common");
const bullmq_1 = require("@nestjs/bullmq");
exports.QUEUE_NAMES = {
    WEBHOOKS: 'webhooks',
    PAYMENTS: 'payments',
    PDF_GENERATION: 'pdf_generation',
    VECTOR_INDEXING: 'vector_indexing',
    NOTIFICATIONS: 'notifications',
    VIRUS_SCAN: 'virus_scan',
    PRICING_RECALC: 'pricing_recalc',
};
let WorkersProducersModule = class WorkersProducersModule {
};
exports.WorkersProducersModule = WorkersProducersModule;
exports.WorkersProducersModule = WorkersProducersModule = __decorate([
    (0, common_1.Module)({
        imports: [
            bullmq_1.BullModule.registerQueue({ name: exports.QUEUE_NAMES.WEBHOOKS }, { name: exports.QUEUE_NAMES.PAYMENTS }, { name: exports.QUEUE_NAMES.PDF_GENERATION }, { name: exports.QUEUE_NAMES.VECTOR_INDEXING }, { name: exports.QUEUE_NAMES.NOTIFICATIONS }, { name: exports.QUEUE_NAMES.VIRUS_SCAN }, { name: exports.QUEUE_NAMES.PRICING_RECALC }),
        ],
        exports: [bullmq_1.BullModule],
    })
], WorkersProducersModule);
//# sourceMappingURL=workers-producers.module.js.map