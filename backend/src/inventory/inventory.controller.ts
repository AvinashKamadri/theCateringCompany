import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import {
  DishIngredientDto,
  InventoryService,
  StockLogDto,
  UpsertDishDto,
  UpsertIngredientDto,
} from './inventory.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { Public } from '../common/decorators/public.decorator';

type Caller = { userId: string; email: string };

@Controller('inventory')
@UseGuards(AuthGuard('jwt'))
export class InventoryController {
  constructor(private readonly inventory: InventoryService) {}

  // ingredients
  @Get('ingredients')
  listIngredients(@CurrentUser() user: Caller) {
    return this.inventory.listIngredients(user.email);
  }

  @Get('ingredients/:id')
  getIngredient(@CurrentUser() user: Caller, @Param('id') id: string) {
    return this.inventory.getIngredient(user.email, id);
  }

  @Post('ingredients')
  createIngredient(@CurrentUser() user: Caller, @Body() dto: UpsertIngredientDto) {
    return this.inventory.createIngredient(user.email, user.userId, dto);
  }

  @Patch('ingredients/:id')
  updateIngredient(
    @CurrentUser() user: Caller,
    @Param('id') id: string,
    @Body() dto: Partial<UpsertIngredientDto>,
  ) {
    return this.inventory.updateIngredient(user.email, id, dto);
  }

  @Delete('ingredients/:id')
  deleteIngredient(@CurrentUser() user: Caller, @Param('id') id: string) {
    return this.inventory.deleteIngredient(user.email, id);
  }

  // dishes
  @Get('dishes')
  listDishes(@CurrentUser() user: Caller) {
    return this.inventory.listDishes(user.email);
  }

  @Get('dishes/:id')
  getDish(@CurrentUser() user: Caller, @Param('id') id: string) {
    return this.inventory.getDish(user.email, id);
  }

  @Post('dishes')
  createDish(@CurrentUser() user: Caller, @Body() dto: UpsertDishDto) {
    return this.inventory.createDish(user.email, dto);
  }

  @Patch('dishes/:id')
  updateDish(
    @CurrentUser() user: Caller,
    @Param('id') id: string,
    @Body() dto: Partial<UpsertDishDto>,
  ) {
    return this.inventory.updateDish(user.email, id, dto);
  }

  @Post('dishes/:id/ingredients')
  setDishIngredient(
    @CurrentUser() user: Caller,
    @Param('id') dishId: string,
    @Body() dto: DishIngredientDto,
  ) {
    return this.inventory.setDishIngredient(user.email, dishId, dto);
  }

  @Delete('dishes/:id/ingredients/:ingredientId')
  removeDishIngredient(
    @CurrentUser() user: Caller,
    @Param('id') dishId: string,
    @Param('ingredientId') ingredientId: string,
  ) {
    return this.inventory.removeDishIngredient(user.email, dishId, ingredientId);
  }

  // stock log
  @Post('stock-log')
  logStock(@CurrentUser() user: Caller, @Body() dto: StockLogDto) {
    return this.inventory.logStock(user.email, user.userId, dto);
  }

  @Get('stock-log')
  listStockLog(
    @CurrentUser() user: Caller,
    @Query('ingredient_id') ingredientId?: string,
  ) {
    return this.inventory.listStockLog(user.email, ingredientId);
  }

  // public menu feed — used by the customer-facing menu page
  @Public()
  @Get('menu-feed')
  menuFeed() {
    return this.inventory.listMenuItemsWithDishes();
  }
}
