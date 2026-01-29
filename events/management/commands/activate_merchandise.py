from django.core.management.base import BaseCommand
from events.models_merchandise import Merchandise

class Command(BaseCommand):
    help = 'Update all draft merchandise products to active status'

    def handle(self, *args, **options):
        # Get all draft products
        draft_products = Merchandise.objects.filter(status='draft')
        
        if not draft_products.exists():
            self.stdout.write(self.style.SUCCESS('No draft products found.'))
            return
        
        # Update all draft products to active
        updated_count = draft_products.update(status='active')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} products from draft to active status.')
        )
        
        # Show some details
        active_products = Merchandise.objects.filter(status='active')
        active_with_stock = active_products.filter(stock_quantity__gt=0)
        
        self.stdout.write(f'Total active products: {active_products.count()}')
        self.stdout.write(f'Active products with stock: {active_with_stock.count()}')
        
        # List first few updated products
        for product in active_products[:5]:
            stock_status = "In Stock" if product.stock_quantity > 0 else "Out of Stock"
            self.stdout.write(f'- {product.name}: {stock_status} ({product.stock_quantity} units)')
