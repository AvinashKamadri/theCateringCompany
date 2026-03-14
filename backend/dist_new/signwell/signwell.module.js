"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SignWellModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const signwell_service_1 = require("./signwell.service");
const signwell_controller_1 = require("./signwell.controller");
const contracts_module_1 = require("../contracts/contracts.module");
let SignWellModule = class SignWellModule {
};
exports.SignWellModule = SignWellModule;
exports.SignWellModule = SignWellModule = __decorate([
    (0, common_1.Module)({
        imports: [
            config_1.ConfigModule,
            (0, common_1.forwardRef)(() => contracts_module_1.ContractsModule),
        ],
        controllers: [signwell_controller_1.SignWellController],
        providers: [signwell_service_1.SignWellService],
        exports: [signwell_service_1.SignWellService],
    })
], SignWellModule);
//# sourceMappingURL=signwell.module.js.map