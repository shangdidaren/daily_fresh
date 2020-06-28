from django.contrib import admin

# Register your models here.
from .models import GoodsType,IndexGoodsBanner,IndexPromotionBanner,IndexTypeGoodsBanner,GoodsSKU,Goods
from celery_tasks.tasks import generate_static_index_html
from django.core.cache import cache


class BaseAdmin(admin.ModelAdmin):
    '''

        谁继承在，在添加和删除的时候就会发送网页静态化请求，
        Celery进行处理，牌面

    '''
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        generate_static_index_html.delay()

        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)

        generate_static_index_html.delay()

        cache.delete('index_page_data')


admin.site.register(GoodsType, BaseAdmin)
admin.site.register(IndexGoodsBanner, BaseAdmin)
admin.site.register(IndexPromotionBanner, BaseAdmin)
admin.site.register(IndexTypeGoodsBanner, BaseAdmin)

admin.site.register(GoodsSKU)
admin.site.register(Goods)